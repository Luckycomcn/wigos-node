from django.test import TestCase, TransactionTestCase
from .testing_utils import load_test_json
from .models import Station, WIGOSNodeUser

class StationCreationTestCase(TestCase):
    """WSI 唯一性：主标识与 additionalIds 之间不许重复，也不许跨站重复。

    这些用例原本依赖迁移 0011 灌入的演示站点。0011 现在只在显式开启
    WIGOS_SEED_DEMO 时才灌数据（测试库永不灌），所以样例站点由 setUp 自建 ——
    测试不该把自己的前置条件寄托在生产数据迁移上。
    """

    def setUp(self):
        self.owner = WIGOSNodeUser.objects.create_user(
            username="wsi_owner", email="wsi_owner@example.com", password="pw12345!"
        )
        # 两个样例站点都建，因为标识符交叉在这里：
        #   test_wmdrv2.json              主标识 0-20000-0-123456
        #   test_multiple_wsi_wdmdv2.json 主标识 0-20000-0-12345，
        #                                 additionalIds 0-51-21-2121 / 0-533-1212-12321
        for name in ('test_wmdrv2.json', 'test_multiple_wsi_wdmdv2.json'):
            Station.objects.create(wmdrv2=load_test_json(name), owner=self.owner)

    def test_double_creation_rejected(self):

        wmdrv2_data = load_test_json('test_wmdrv2.json')

        with self.assertRaises(ValueError):
            Station.objects.create(wmdrv2=wmdrv2_data, owner=self.owner)


    def test_primary_wsi_in_additional_identifier_rejected(self):
        wmdrv2_data = load_test_json('test_wmdrv2.json')
        wmdrv2_data['id'] = '0-51-21-2121'         # WSI used in additional identifiers in test station

        with self.assertRaises(ValueError):
            Station.objects.create(wmdrv2=wmdrv2_data, owner=self.owner)



    def test_additional_wsi_in_additional_identifier_rejected(self):
        wmdrv2_data = load_test_json('test_wmdrv2.json')
        wmdrv2_data['id'] = '0-51-21-2121ok'         # WSI not yet used
        wmdrv2_data['properties']['additionalIds'] = ['0-51-21-2121'] # already used in additional identifiers in test station

        with self.assertRaises(ValueError):
            Station.objects.create(wmdrv2=wmdrv2_data, owner=self.owner)


    def test_additional_wsi_in_primary_identifier_rejected(self):
        wmdrv2_data = load_test_json('test_wmdrv2.json')
        wmdrv2_data['id'] = '0-51-21-2121ok'         # WSI not yet used
        wmdrv2_data['properties']['additionalIds'] = ['0-20000-0-123456'] # already used in primary identifier in test station

        with self.assertRaises(ValueError):
            Station.objects.create(wmdrv2=wmdrv2_data, owner=self.owner)
