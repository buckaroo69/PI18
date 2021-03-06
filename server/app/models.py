import uuid

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from timescale.db.models.models import TimescaleModel
from django.contrib.postgres.fields import ArrayField

# Create your models here.

class Simulation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    model = models.TextField()
    learning_rate = models.FloatField()
    isdone = models.BooleanField()
    isrunning = models.BooleanField()
    biases = models.BinaryField()
    layers = models.IntegerField()
    epoch_interval = models.IntegerField(validators=[MinValueValidator(1)])
    goal_epochs = models.IntegerField()
    metrics = ArrayField(models.CharField(max_length=60))
    error_text = models.CharField(max_length=500, blank=True, default="")
    def get_current_epoch(self):
        updateSet = Update.objects.filter(sim=self.id)
        if len(updateSet) > 0:
            return updateSet.latest('time')
        return None
    current_epoch = property(get_current_epoch)

    #insert more stats/goals here
    class Meta:
        db_table = "simulations"


class Update(TimescaleModel):
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    epoch = models.IntegerField()
    loss = models.FloatField()
    accuracy = models.FloatField()
    val_loss = models.FloatField()
    val_accuracy = models.FloatField()
    class Meta:
        db_table = "epoch_values"
        indexes = [models.Index(fields=["sim","epoch"])]

class Weights(TimescaleModel):
    epoch = models.IntegerField()
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    layer_index = models.IntegerField()
    layer_name = models.CharField(max_length=150)
    weight = ArrayField(models.FloatField())
    class Meta:
        db_table = "weights"
        indexes =[ models.Index(fields=['sim','epoch']),models.Index(fields=['sim','layer_index'])]

class Tagged(models.Model):
    tag = models.CharField(max_length=200)
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    tagger = models.ForeignKey(User,on_delete=models.CASCADE)
    iskfold = models.BooleanField(default=False)
    class Meta:
        unique_together = (('tag','sim'),)
        db_table = "Tags"
        indexes = [models.Index(fields=['tag']),models.Index(fields=['tagger']),models.Index(fields=["sim"])]

class ExtraMetrics(TimescaleModel):
    epoch = models.IntegerField()
    sim = models.ForeignKey(Simulation, on_delete=models.CASCADE)
    value = models.FloatField()
    metric = models.CharField(max_length=60)
    class Meta:
        db_table = "extra_metrics"
        indexes =[ models.Index(fields=['sim','epoch']),models.Index(fields=['sim','metric'])]