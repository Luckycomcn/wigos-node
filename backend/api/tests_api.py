from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


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

    def test_check_wigosidentifiers_partial_secondary_identifier(self):
        """Test that a prefix or suffix of an existing secondary WIGOS identifier is not reported as taken."""
        self.checkwsi_url = reverse('check_wigosidentifiers')
        # the test station has additional identifiers 0-51-21-2121 and 0-533-1212-12321
        partial = ['0-51-21-212', '0-533-1212-1232', '-51-21-2121', '1-2121']
        response = self.client.get(self.checkwsi_url, {'wigos_identifier': partial})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {wsi: False for wsi in partial})