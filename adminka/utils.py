from flask_admin.contrib.sqla.filters import BaseSQLAFilter


class FilterPaidPayments(BaseSQLAFilter):
    def apply(self, query, value, alias=None):
        if value == 'done':
            return query.filter(self.column == 'done')

    def operation(self):
        return 'is'
