# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/tests/integration/dynamodb2/test_layer1.py#L88-L107
# smelly line(s) in the original file: 88
# smelly line(s) in this file: 8
# ids: pysmell_1831
# note: Python 2 era source, kept as found
def create_table(self, table_name, attributes, schema,
                 provisioned_throughput, lsi=None, wait=True):
    # Note: This is a slightly different ordering that makes less sense.
    result = self.dynamodb.create_table(
        attributes,
        table_name,
        schema,
        provisioned_throughput,
        local_secondary_indexes=lsi
    )
    self.addCleanup(self.dynamodb.delete_table, table_name)
    if wait:
        while True:
            description = self.dynamodb.describe_table(table_name)
            if description['Table']['TableStatus'].lower() == 'active':
                return result
            else:
                time.sleep(5)
    else:
        return result
