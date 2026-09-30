from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Station



class StationAPITestCase(APITestCase):

    def test_check_wigosidentifiers(self):
        """Test that a GET request successfully retrieves WIGOS identifier checks."""
        self.checkwsi_url = reverse('check_wigosidentifiers')
        response = self.client.get(self.checkwsi_url, {'wigos_identifier': '1-123-456-ABC'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['1-123-456-ABC'], False)

    def test_check_wigosidentifiers_no_identifiers(self):
        """Test that a GET request without WIGOS identifiers returns a 400 error."""
        self.checkwsi_url = reverse('check_wigosidentifiers')
        response = self.client.get(self.checkwsi_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['detail'], "No WIGOS identifiers provided")

    def test_check_wigosidentifiers_existing_primary_identifier(self):
        """Test that a GET request with an existing WIGOS identifier returns True."""
        # First, create a station with a known WIGOS identifier
        self.checkwsi_url = reverse('check_wigosidentifiers')
        response = self.client.get(self.checkwsi_url, {'wigos_identifier': '0-20000-0-123456'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['0-20000-0-123456'], True)


    def test_check_wigosidentifiers_existing_secondary_identifier(self):
        """Test that a GET request with an existing secondary WIGOS identifier returns True."""
        # First, create a station with a known secondary WIGOS identifier
        self.checkwsi_url = reverse('check_wigosidentifiers')
        response = self.client.get(self.checkwsi_url, {'wigos_identifier': '0-533-1212-12321'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['0-533-1212-12321'], True)