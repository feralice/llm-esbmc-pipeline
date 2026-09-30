# smell: MultiplyNestedContainer
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/tests/integration/dynamodb2/test_layer1.py#L36-L86
# smelly line(s) in the original file: 69
# smelly line(s) in this file: 41
# ids: pysmell_2351
# note: Python 2 era source, kept as found
def setUp(self):
    self.dynamodb = DynamoDBConnection()
    self.table_name = 'test-%d' % int(time.time())
    self.hash_key_name = 'username'
    self.hash_key_type = 'S'
    self.range_key_name = 'date_joined'
    self.range_key_type = 'N'
    self.read_units = 5
    self.write_units = 5
    self.attributes = [
        {
            'AttributeName': self.hash_key_name,
            'AttributeType': self.hash_key_type,
        },
        {
            'AttributeName': self.range_key_name,
            'AttributeType': self.range_key_type,
        }
    ]
    self.schema = [
        {
            'AttributeName': self.hash_key_name,
            'KeyType': 'HASH',
        },
        {
            'AttributeName': self.range_key_name,
            'KeyType': 'RANGE',
        },
    ]
    self.provisioned_throughput = {
        'ReadCapacityUnits': self.read_units,
        'WriteCapacityUnits': self.write_units,
    }
    self.lsi = [
        {
            'IndexName': 'MostRecentIndex',
            'KeySchema': [
                {
                    'AttributeName': self.hash_key_name,
                    'KeyType': 'HASH',
                },
                {
                    'AttributeName': self.range_key_name,
                    'KeyType': 'RANGE',
                },
            ],
            'Projection': {
                'ProjectionType': 'KEYS_ONLY',
            }
        }
    ]
