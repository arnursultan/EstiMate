import logging
from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Store

logger = logging.getLogger(__name__)

class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = '__all__'

    def update(self, instance, validated_data):
        new_payment = validated_data.pop("payment", None)
        status_changed = False

        if new_payment is not None and new_payment > 0:
            if instance.debt == 0:
                raise ValidationError("Ошибка: Долг уже погашен. Новый платеж невозможен.")

            if new_payment > instance.debt:
                raise ValidationError(
                    f"Ошибка: Платеж {new_payment} превышает текущий долг {instance.debt}."
                )

            old_debt = instance.debt
            instance.debt = max(instance.debt - new_payment, 0)
            instance.payment += new_payment

            if instance.debt == 0:
                instance.status = "closed"
                status_changed = True

            logger.info(
                f"💰 Магазин {instance.name} внес {new_payment} KGS. "
                f"Долг был {old_debt}, стал {instance.debt}."
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if status_changed:
            logger.info(f"✅ Магазин {instance.name} полностью погасил долг и теперь закрыт.")

        return instance
