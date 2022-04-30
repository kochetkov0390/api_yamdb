import datetime as dt
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework import serializers
from rest_framework.relations import SlugRelatedField
from rest_framework.validators import UniqueValidator

from reviews.models import (Review, Comment, User, EmailAndCode,
                            Category, Genre, Title)


class UserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name',
                  'bio', 'email', 'role']

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username is not unique')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email is not unique')
        return value


class GetTokenSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    confirmation_code = serializers.CharField(required=True)
    expire_date = serializers.DateTimeField(required=False)

    def validate(self, data):
        username = data['username']
        confirm_code = data['confirmation_code']
        if not EmailAndCode.objects.filter(
                username=username, confirm_code=confirm_code).exists():
            raise serializers.ValidationError('Invalid confirmation code')
        return data

    def validate_username(self, value):
        if not User.objects.filter(username=value).exists():
            raise Http404
        return value

    class Meta:
        model = EmailAndCode
        fields = ['username', 'confirmation_code', 'expire_date']


class ConfirmEmailSerializer(serializers.ModelSerializer):
    username = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    confirm_code = serializers.CharField(required=False)
    expire_date = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        email = validated_data.get('email')
        try:
            instance = EmailAndCode.objects.get(email=email)
            return self.update(instance, validated_data)
        except ObjectDoesNotExist:
            return EmailAndCode.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.confirm_code = validated_data.get(
            'confirm_code')
        instance.expire_date = validated_data.get(
            'expire_date')
        instance.save()
        return instance

    def validate_username(self, value):
        if value == 'me' or User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Invalid username')
        return value

    def validate_email(self, value):
        if (EmailAndCode.objects.filter(email=value).exists()
                or User.objects.filter(email=value).exists()):
            raise serializers.ValidationError('Email already exists')
        return value

    class Meta:
        model = EmailAndCode
        fields = ['username', 'email', 'confirm_code', 'expire_date']


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ('name', 'slug')
        lookup_field = 'slug'


class GenreSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    slug = serializers.CharField(required=True,
                                 validators=[UniqueValidator(
                                     queryset=Genre.objects.all())])

    class Meta:
        model = Genre
        fields = ('name', 'slug')
        lookup_field = 'slug'


class ReadTitleSerializer(serializers.ModelSerializer):

    category = CategorySerializer()
    genre = GenreSerializer(many=True, source='genres')
    rating = serializers.IntegerField(read_only=True)

    class Meta:
        model = Title
        fields = ('id', 'name', 'year', 'rating',
                  'description', 'genre', 'category')
        read_only_fields = ('category', 'genres')

    # def get_rating(self, obj):
    #     reviews = obj.reviews.all()
    #     if reviews:
    #         rating = reviews.aggregate(Avg('score'))
    #         obj.rating = round(rating.get('score__avg'))
    #         obj.save()
    #         return obj.rating
    #     return None


class WriteTitleSerializer(serializers.ModelSerializer):
    category = SlugRelatedField(
        slug_field='slug',
        queryset=Category.objects.all(),
        required=True
    )
    genre = SlugRelatedField(
        slug_field='slug',
        queryset=Genre.objects.all(),
        many=True,
        required=True,
        source='genres'
    )

    class Meta:
        model = Title
        fields = ('id', 'name', 'year', 'description', 'genre', 'category')

    def validate_year(self, value):
        current_year = dt.date.today().year
        if current_year < value:
            raise serializers.ValidationError(
                'Нельзя добавлять произведения, которые еще не вышли'
            )
        return value


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        default=serializers.CurrentUserDefault(),
        read_only=True,
    )

    class Meta:
        model = Review
        fields = ('id', 'text', 'author', 'score', 'pub_date')


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(
        slug_field='username',
        default=serializers.CurrentUserDefault(),
        read_only=True
    )

    def validate_author(self, value):
        return self.context['request'].user

    class Meta:
        model = Comment
        fields = ('id', 'text', 'author', 'pub_date')
