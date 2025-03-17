# from django.test import TestCase
# from django.core.files.base import ContentFile
# from apps.products.models import Product, ProductCategory, ProductImage
# from django.contrib.auth import get_user_model
# from io import BytesIO
# from PIL import Image
# import random
#
# User = get_user_model()
#
# class ProductTestCase(TestCase):
#     def setUp(self):
#         self.admin = User.objects.create_superuser(
#             email="admin@example.com",
#             password="testpassword",
#             phone="123456789"
#         )
#
#         self.categories = [
#             ProductCategory.objects.create(name=f"Категория {i}") for i in range(1, 4)
#         ]
#
#         self.products = []
#         for i in range(10):
#             product = Product.objects.create(
#                 name=f"Товар {i+1}",
#                 description=f"Описание товара {i+1}",
#                 price=random.randint(100, 5000),
#                 category=random.choice(self.categories),
#                 stock=random.randint(1, 100),
#                 owner=self.admin,
#                 status="available",
#             )
#             self.products.append(product)
#
#             image = self.add_fake_image(product)
#             print(f"✅ Добавлено изображение {image.image} для товара {product.name}")
#
#     def add_fake_image(self, product):
#         img_io = BytesIO()
#         img = Image.new("RGB", (100, 100), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
#         img.save(img_io, format="JPEG")
#         img_io.seek(0)
#
#         image = ProductImage.objects.create(
#             product=product,
#             image=ContentFile(img_io.getvalue(), name=f"fake_image_{random.randint(1, 10000)}.jpg"),
#             is_main=random.choice([True, False])
#         )
#
#         image.save()
#         return image
#
#     def test_product_creation(self):
#         self.assertEqual(Product.objects.count(), 10)
#         self.assertEqual(ProductCategory.objects.count(), 3)
#
#     def test_product_images(self):
#         for product in self.products:
#             print(f"🔍 Проверяем изображения для {product.name}: {product.images.count()}")
#             self.assertTrue(product.images.exists(), f"❌ У товара {product.name} нет изображения!")
#
#     def test_api_product_list(self):
#         response = self.client.get("/api/products/products/")
#         self.assertEqual(response.status_code, 200)
#         self.assertGreaterEqual(len(response.json()), 10)
