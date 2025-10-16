
import graphene
from crm.schema import Query as CRMQuery, Mutation as CRMMutation


# Extend CRMQuery by adding your own fields (like 'hello')
class Query(CRMQuery, graphene.ObjectType):
    hello = graphene.String(default_value="Hello, GraphQL!")


# Extend CRMMutation (you can also add custom mutations later)
class Mutation(CRMMutation, graphene.ObjectType):
    pass


# Define the schema
schema = graphene.Schema(query=Query, mutation=Mutation)
