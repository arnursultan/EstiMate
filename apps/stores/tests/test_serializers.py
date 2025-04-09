import pytest
from rest_framework.exceptions import ValidationError
from apps.stores.serializers import StoreSerializer, StoreStatusUpdateSerializer, StoreDebtSerializer, \
    StoreDetailSerializer, StoreActivationSerializer
from apps.stores.models import Store, City, StoreDebt
from apps.users.models import User
from rest_framework.test import APIRequestFactory


@pytest.mark.django_db
def test_store_serializer_validate_inn():
    city = City.objects.create(name="TestCity")
    Store.objects.create(name="Existing", inn="1234567890", city=city, address="A", phone="+996700000000")

    serializer = StoreSerializer(data={
        "name": "NewStore",
        "inn": "1234567890",  # duplicate
        "city": city.id,
        "address": "B",
        "phone": "+996700000001"
    })

    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "уже существует" in str(e.value)


@pytest.mark.django_db
def test_store_serializer_invalid_phone():
    city = City.objects.create(name="TestCity")
    serializer = StoreSerializer(data={
        "name": "BadPhone",
        "inn": "1234567891",
        "city": city.id,
        "address": "Test",
        "phone": "0070000000"
    })
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "в формате" in str(e.value)


@pytest.mark.django_db
def test_store_serializer_create_sets_creator():
    user = User.objects.create_user(email="test@example.com", phone="+996700000011", password="123", first_name="T", last_name="U", status="approved")
    city = City.objects.create(name="City")
    factory = APIRequestFactory()
    request = factory.post("/fake-url/")
    request.user = user

    serializer = StoreSerializer(
        data={"name": "NewStore", "inn": "1234567899", "city": city.id, "address": "X", "phone": "+996700000099"},
        context={"request": request}
    )

    assert serializer.is_valid(), serializer.errors
    instance = serializer.save()
    assert instance.creator == user



@pytest.mark.django_db
def test_status_update_invalid_status():
    store = Store.objects.create(name="Test", inn="123", city=City.objects.create(name="X"), address="A", phone="+996", status="pending")
    serializer = StoreStatusUpdateSerializer(instance=store, data={"status": "invalid"})
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)


@pytest.mark.django_db
def test_status_update_not_pending():
    store = Store.objects.create(name="Test", inn="123", city=City.objects.create(name="X"), address="A", phone="+996", status="approved")
    serializer = StoreStatusUpdateSerializer(instance=store, data={"status": "rejected"})
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)



@pytest.mark.django_db
def test_store_debt_creator_name():
    user = User.objects.create_user(email="p@example.com", phone="+9961", password="123", first_name="P", last_name="User", status="approved")
    city = City.objects.create(name="X")
    store = Store.objects.create(name="S", inn="12345", city=city, address="A", phone="+996", status="approved")
    debt = store.debts.create(amount=1000, created_by=user)

    serializer = StoreDebtSerializer(debt)
    assert serializer.data["creator_name"] == "P User"


@pytest.mark.parametrize("inn", ["123", "123456789012345"])
@pytest.mark.django_db
def test_store_serializer_inn_length(inn):
    city = City.objects.create(name="X")
    serializer = StoreSerializer(data={
        "name": "BadINN",
        "inn": inn,
        "city": city.id,
        "address": "A",
        "phone": "+996700000000"
    })
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)


@pytest.mark.django_db
def test_store_serializer_phone_plus_only():
    city = City.objects.create(name="X")
    serializer = StoreSerializer(data={
        "name": "PhoneOnlyPlus",
        "inn": "1234567890",
        "city": city.id,
        "address": "A",
        "phone": "+"
    })
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)



@pytest.mark.django_db
def test_status_update_already_approved():
    store = Store.objects.create(name="S", inn="123", city=City.objects.create(name="C"), address="A", phone="+996", status="approved")
    serializer = StoreStatusUpdateSerializer(instance=store, data={"status": "approved"})
    with pytest.raises(ValidationError) as e:
        serializer.is_valid(raise_exception=True)
    assert "только для заявок" in str(e.value).lower()



@pytest.mark.django_db
def test_store_debt_creator_none():
    store = Store.objects.create(name="S", inn="123", city=City.objects.create(name="C"), address="A", phone="+996")
    debt = store.debts.create(amount=1500, created_by=None)
    serializer = StoreDebtSerializer(debt)
    assert serializer.data["creator_name"] is None


from apps.stores.serializers import DebtPaymentSerializer

@pytest.mark.django_db
def test_debt_payment_negative_amount():
    serializer = DebtPaymentSerializer(data={"debt_id": 1, "payment_amount": -100})
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)



@pytest.mark.django_db
def test_store_detail_serializer_total_debt():
    city = City.objects.create(name="TestCity")
    store = Store.objects.create(name="TestStore", inn="9876543210", city=city, address="Addr", phone="+996700000000")

    StoreDebt.objects.create(store=store, amount=1000, is_paid=False)
    StoreDebt.objects.create(store=store, amount=500, is_paid=True)
    StoreDebt.objects.create(store=store, amount=2000, is_paid=False)

    serializer = StoreDetailSerializer(store)
    assert serializer.data["total_debt"] == 3000  # only unpaid

@pytest.mark.django_db
def test_store_detail_creator_name_null_safe():
    city = City.objects.create(name="TestCity")
    store = Store.objects.create(name="NamelessStore", inn="9876543211", city=city, address="Addr", phone="+996700000001", creator=None)

    serializer = StoreDetailSerializer(store)
    assert serializer.data["creator_name"] is None


@pytest.mark.django_db
def test_store_activation_serializer():
    store = Store.objects.create(
        name="Inactive", inn="1234567890", city=City.objects.create(name="X"),
        address="Y", phone="+996700000001", is_active=False
    )

    serializer = StoreActivationSerializer(instance=store, data={"is_active": True})
    assert serializer.is_valid()
    instance = serializer.save()
    assert instance.is_active is True


from apps.stores.serializers import StoreDebtPaymentSerializer

@pytest.mark.django_db
def test_store_debt_payment_only_true():
    debt = StoreDebt.objects.create(store=Store.objects.create(name="S", inn="X", city=City.objects.create(name="C"), address="A", phone="+996"),amount=1000)
    serializer = StoreDebtPaymentSerializer(instance=debt, data={"is_paid": False})
    with pytest.raises(ValidationError):
        serializer.is_valid(raise_exception=True)

@pytest.mark.django_db
def test_store_debt_payment_already_paid():
    debt = StoreDebt.objects.create(
        store=Store.objects.create(
            name="S", inn="X", city=City.objects.create(name="C"), address="A", phone="+996"
        ),
        amount=1000,
        is_paid=True
    )
    serializer = StoreDebtPaymentSerializer(instance=debt, data={"is_paid": True})
    assert serializer.is_valid()
    with pytest.raises(ValidationError):
        serializer.save()

