from config import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models
from jsonpath_ng import parse

json_update_dict = {
    "name" : parse('$.properties.title')
}
location_expression = parse('$.geometry.coordinates')
wigos_identifier_expression = parse('$.id')

class WIGOSNodeUser(AbstractUser):
    # 1. Require a unique email address
    email = models.EmailField(unique=True)

    # 2. Tell Django to use email as the login identifier
    USERNAME_FIELD = 'email'

    # 3. Specify fields prompted for when running 'createsuperuser'
    REQUIRED_FIELDS = ['username'] 

    def __str__(self):
        return self.email

class Station(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    wigos_identifier = models.CharField(max_length=100, unique=True, db_index=True)
    location = gis_models.PointField(srid=4326, null=False, blank=False)
    
    wmdrv2 = models.JSONField(null=False, blank=False)

    owner = models.ForeignKey("WIGOSNodeUser", on_delete=models.CASCADE, related_name='stations')

    def get_wigos_identifiers(self):
        wsis = []
        if self.wmdrv2:
            wsi = wigos_identifier_expression.find(self.wmdrv2)
            if wsi and len(wsi) > 0:
                wsis.append(wsi[0].value)
        return wsis

    def save(self, *args, **kwargs):
        """override save method to update name and location from wmdrv2 JSON data"""

        wigos_identifier_value = wigos_identifier_expression.find(self.wmdrv2)
        if not wigos_identifier_value or len(wigos_identifier_value) == 0:
            raise ValueError("Missing required field 'id' in wmdrv2 JSON data")
        self.wigos_identifier = wigos_identifier_value[0].value

        if Station.objects.filter(wigos_identifier=self.wigos_identifier).exclude(pk=self.pk).exists():
            raise ValueError(f"WIGOS identifier '{self.wigos_identifier}' is already in use")

        for key, jsonpath_expression in json_update_dict.items():
            value = jsonpath_expression.find(self.wmdrv2)

            if not value or len(value) == 0:
                raise ValueError(f"Missing required field '{key}' in wmdrv2 JSON data")

            self.__dict__[key] = value[0].value

        location_value = location_expression.find(self.wmdrv2)
        if not location_value or len(location_value) == 0 or (len(location_value[0].value) != 2 and len(location_value[0].value) != 3):
            raise ValueError("Missing required field 'location' in wmdrv2 JSON data")

    
        self.location = Point(x=location_value[0].value[0], y=location_value[0].value[1], srid=4326)
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name + " (" + self.wigos_identifier + ")"
