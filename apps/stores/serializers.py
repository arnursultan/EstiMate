import logging
from rest_framework import serializers
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
            old_debt = instance.debt
            instance.debt = max(instance.debt - new_payment, 0)
            instance.payment += new_payment

            if instance.debt == 0:
                instance.status = "closed"
                status_changed = True

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if new_payment:
            logger.info(
                f"💰 Магазин {instance.name} внес {new_payment} KGS. "
                f"Долг был {old_debt}, стал {instance.debt}."
            )

        if status_changed:
            logger.info(f"✅ Магазин {instance.name} полностью погасил долг и теперь закрыт.")

        return instance
