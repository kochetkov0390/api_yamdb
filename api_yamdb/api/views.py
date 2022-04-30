import datetime as dt

from django.db.models import Avg
from django.db.utils import IntegrityError
from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, filters, mixins
from rest_framework.permissions import (AllowAny,
                                        IsAuthenticatedOrReadOnly,
                                        IsAuthenticated)
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.decorators import permission_classes, api_view, action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework_simplejwt.tokens import AccessToken
from reviews.models import (User, Review, Genre, UserRole,
                            Title, Category, EmailAndCode)

from .permissions import (ReviewAndComment, AdminModifyOrReadOnlyPermission,
                          IsAdmin)
from .serializers import (UserSerializer,
                          ReviewSerializer, CommentSerializer,
                          CategorySerializer, GenreSerializer,
                          ReadTitleSerializer, WriteTitleSerializer,
                          GetTokenSerializer, ConfirmEmailSerializer)
from .filters import TitleFilter


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = LimitOffsetPagination
    permission_classes = [AdminModifyOrReadOnlyPermission, ]
    lookup_field = 'username'

    def perform_create(self, serializer):
        if 'role' not in serializer.validated_data:
            serializer.save(role=UserRole.USER)
        else:
            serializer.save()

    @action(detail=False, methods=['get', 'patch'],
            permission_classes=[IsAuthenticated])
    def me(self, request):
        """API для получения и редактирования
        текущим пользователем своих данных"""
        user = request.user
        if request.method == 'GET':
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(role=user.role, partial=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def get_token(request):
    EmailAndCode.objects.filter(expire_date__lte=timezone.now()).delete()
    serializer = GetTokenSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = serializer.validated_data.get('username')
    conf_code = serializer.validated_data.get('confirmation_code')
    conf_user = get_object_or_404(
        EmailAndCode,
        username=username,
        confirm_code=conf_code
    )

    user = get_object_or_404(User, username=conf_user.username)
    conf_user.delete()
    token = AccessToken.for_user(user)
    return Response({'token': str(token)},
                    status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_email(request):
    EmailAndCode.objects.filter(expire_date__lte=timezone.now()).delete()
    serializer = ConfirmEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data.get('email')
    username = serializer.validated_data.get('username')
    conf_code = User.objects.make_random_password(length=16)
    expr_date = timezone.now() + dt.timedelta(minutes=5)

    user = User.objects.create_user(username=username,
                                    email=email)

    send_mail(
        'Email confirmation',
        f'Your confirmation code: {conf_code}',
        'yamdb@yandex.com',
        [user.email, ]
    )
    serializer.save(confirm_code=conf_code,
                    expire_date=expr_date)

    return Response(
        data={'email': email, 'username': username},
        status=status.HTTP_200_OK
    )


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    pagination_class = LimitOffsetPagination
    permission_classes = [ReviewAndComment, IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        title = get_object_or_404(Title, id=self.kwargs['title_id'])
        return title.reviews.all()

    def get_serializer_context(self):
        context = super(ReviewViewSet, self).get_serializer_context()
        context.update({"title_id": self.kwargs['title_id']})
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
        except IntegrityError:
            return Response('Only one review per title',
                            status=status.HTTP_400_BAD_REQUEST)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data,
                        status=status.HTTP_201_CREATED,
                        headers=headers)

    def perform_create(self, serializer):
        title = get_object_or_404(Title,
                                  id=self.kwargs['title_id'])
        author = get_object_or_404(User,
                                   username=self.request.user)
        serializer.save(title=title,
                        author=author)


class CommentViewSet(viewsets.ModelViewSet):

    serializer_class = CommentSerializer
    pagination_class = LimitOffsetPagination
    permission_classes = [ReviewAndComment, IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        title = get_object_or_404(Title,
                                  id=self.kwargs['title_id'])
        review = get_object_or_404(Review,
                                   id=self.kwargs['review_id'],
                                   title=title.id)
        return review.comments.all()

    def perform_create(self, serializer):
        review = get_object_or_404(Review,
                                   id=self.kwargs['review_id'])
        author = get_object_or_404(User,
                                   username=self.request.user)

        serializer.save(review_id=review,
                        author=author)


class ListCreateDeleteViewSet(mixins.ListModelMixin,
                              mixins.CreateModelMixin,
                              mixins.DestroyModelMixin,
                              viewsets.GenericViewSet):
    pass


class CategoryViewSet(ListCreateDeleteViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filter_backends = (filters.SearchFilter,)
    search_fields = ['name', ]
    pagination_class = LimitOffsetPagination
    http_method_names = ['get', 'post', 'delete']

    # Check permission does not work as planned
    permission_classes = [IsAdmin]
    lookup_field = 'slug'


class GenreViewSet(ListCreateDeleteViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    filter_backends = (filters.SearchFilter, )
    search_fields = ('name',)
    pagination_class = LimitOffsetPagination

    # Check permission does not work as planned
    permission_classes = [IsAdmin]
    lookup_field = 'slug'


class TitleViewSet(viewsets.ModelViewSet):
    queryset = Title.objects.annotate(
        rating=Avg('reviews__score')
    ).all()
    permission_classes = [IsAdmin]
    pagination_class = LimitOffsetPagination
    filterset_class = TitleFilter

    def get_serializer_class(self):
        if self.action == 'list' or self.action == 'retrieve':
            return ReadTitleSerializer
        return WriteTitleSerializer
