# SQLAudit

SQLAudit is a SQLAlchemy extension that provides structured auditing for ORM models. It automatically records changes to specified fields, including timestamps and the responsible user, with minimal configuration.
It is designed to work with SQLAlchemy's ORM and provides a simple way to track changes to your models without having to write custom code for each model. SQLAudit only requires you to decorate your models with the `@track_table` decorator, and it will automatically track changes to the specified fields.

```python
@track_table(tracked_fields=["name", "email", "created_by_user_id"])
class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
```

## Notice  

This project is in its early stages and is not yet ready for production use.

## Quick start

To get started with `SQLAudit`, you need to install it using pip:

```bash
pip install sqlaudit
```

Follow the steps below to set up and use `SQLAudit` in your SQLAlchemy application.

This short guide demonstrates how to setup and use `SQLAudit` and allow the tracking of changes to your SQLAlchemy models, which will also include the user who made the change.

### Step 1: Define your Base and User model

We will first create a very simple in-memory SQLite database to demonstrate how to use `SQLAudit`. You can use any database supported by SQLAlchemy, but for simplicity, we will use an in-memory SQLite database. As previously mentioned, we will also want to track which user made the changes to the models. Thus we also define a `User` model.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Create an in-memory SQLite database
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[string] = mapped_column()


```

### Step 2: Configure SQLAudit  

The configuration for `SQLAudit` is done using the `SQLAuditConfig` class. We create a configuration object that specifies the session factory, user model, and a callback to get the user ID from the instance.

We need five things to configure SQLAudit:

1. `session_factory`: A session factory that returns a SQLAlchemy session.
2. `user_model`: A user model that represents the user who made the changes.
3. `user_model_user_id_field`: A field in the user model that represents the user ID.
4. `get_user_id_callback`: A callback function that retrieves the user ID from the instance. In this example, we will use a mock function to get the user ID, however in a real application, you could for example use contextvars.

```python
from sqlaudit.config import SQLAuditConfig, set_config

def get_db():
    """Yield a database session for an in-memory SQLite DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_id_mock()
    """Mock function to get user ID from an instance."""
    return 1


config = SQLAuditConfig(
    session_factory=get_db,
    user_model=User,
    user_model_user_id_field="user_id",
    get_user_id_callback=get_user_id_from_instance,
)

set_config(config) # We set the global configuration for SQLAudit
```

### Step 3: Add SQLAudit to your models  

To enable auditing for your models use the `@track_table` decorator. This decorator will automatically track changes to the model and store them in the audit table. There are various options you can pass to the decorator to customize the behavior. The most basic usage only requires a list of strings representing the columns you want to track.

```python
from sqlaudit.decorators import track_table
from sqlalchemy import Integer, String, ForeignKey

@track_table(tracked_fields=["name", "email", "user_id"])
class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
```

#### Step 4: Register the SQLAudit hooks

SQLAudit uses two SQLAlchemy events to track changes: `before_flush` and `after_flush`. You need to register these hooks to enable auditing.

We will be doing this in a `startup` function that will be called when the application starts.

```python
from sqlaudit.hooks import register_hooks

if __name__ == "__main__":
    Base.metadata.create_all(engine)

    register_hooks()
```

### Step 5: Use the session to make changes

Now you can use the session to make changes to your models. SQLAudit will automatically track these changes and store them in the audit table.

```python
from sqlaudit.retrieval import get_resource_changes

with next(get_db()) as session:
    user = User()
    session.add(user)
    session.commit()

    new_customer = Customer(
        name="John Doe", email="jdoe@example.com", user_id=user.user_id
    )

    session.add(new_customer)

    session.commit()
    print(
        f"Customer {new_customer.customer_id} added with name {new_customer.name} and email {new_customer.email}."
    )

    new_customer2 = Customer(
        name="Jane Doe", email="jane@example.com", user_id=user.user_id
    )

    session.add(new_customer2)

    session.commit()
    print(
        f"Customer {new_customer2.customer_id} added with name {new_customer2.name} and email {new_customer2.email}."
    )

    session.refresh(new_customer2)

    new_customer2.name = "Jane Smith"

    session.commit()

    changes = get_resource_changes(
        model_class=Customer,
        session=session,
        filter_resource_ids=["1,", "2"],
        filter_user_ids=str(user.user_id), # Our mock user ID will return a 1 
    )

    for change in changes:
        print(
            f"FIELD: '{change.field_name}' CHANGED AT {str(change.timestamp)} TO {change.new_value} (OLD: {change.old_value}) BY USER ID {change.changed_by}"
        )

```

<!-- Make a full script but make a spoiler -->

### Full Example Script

<details>
<summary>Click to expand the full example script</summary>

```python
from sqlalchemy import ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from sqlaudit.config import SQLAuditConfig, set_config
from sqlaudit.decorators import track_table
from sqlaudit.hooks import register_hooks
from sqlaudit.retrieval import get_resource_changes


# Create an in-memory SQLite database
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Helper function to get a database session.
    This function is used to provide a database session to the application.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    """
    Base class for declarative class definitions.
    """

    pass


# Define the User model
class User(Base):
    """
    User model representing users in the system.
    """

    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Add more columns as needed


# Create a user instance
user = User()


def get_user_id_from_instance() -> int:
    """
    Returns the user_id from the instance.
    This function is used to retrieve the user ID for auditing purposes.
    """
    return user.user_id


# Set the global audit configuration
config = SQLAuditConfig(
    session_factory=get_db,
    user_model=User,
    user_model_user_id_field="user_id",
    get_user_id_callback=get_user_id_from_instance,
)
set_config(config)


# Define the Customer model with tracked fields for auditing
@track_table(tracked_fields=["name", "email", "user_id"], table_label="Customer")
class Customer(Base):
    """
    Customer model representing customers in the system.
    This model is tracked for changes in the specified fields.
    """

    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False)


if __name__ == "__main__":
    # Create all tables in the database
    Base.metadata.create_all(engine)

    # Get a database session
    with next(get_db()) as session:
        # Register hooks for auditing
        register_hooks()

        # Add the user to the session and commit
        session.add(user)
        session.commit()

        # Create and add a new customer
        new_customer = Customer(
            name="John Doe", email="jdoe@example.com", user_id=user.user_id
        )

        session.add(new_customer)
        session.commit()

        print(
            f"Customer {new_customer.customer_id} added with name {new_customer.name} and email {new_customer.email}."
        )

        # Check if the customer is in the database
        customer = (
            session.query(Customer)
            .filter_by(customer_id=new_customer.customer_id)
            .first()
        )

        # Create and add another customer
        new_customer2 = Customer(
            name="Jane Doe", email="jane@example.com", user_id=user.user_id
        )

        session.add(new_customer2)
        session.commit()

        print(
            f"Customer {new_customer2.customer_id} added with name {new_customer2.name} and email {new_customer2.email}."
        )

        # Refresh the session and update the customer's name so we have some more data to track
        session.refresh(new_customer2)
        new_customer2.name = "Jane Smith"
        session.commit()

        # Retrieve and print changes for the customers
        changes = get_resource_changes(
            model_class=Customer,
            session=session,
            filter_resource_ids=new_customer2.customer_id,
        )

        for change in changes:
            print(
                f"FIELD: '{change.field_name}' CHANGED AT {str(change.timestamp)} TO {change.new_value} (OLD: {change.old_value}) BY USER ID {change.changed_by}"
            )

```

</details>

## Documentation

### `sqlaudit.retrieval.get_resource_changes()`

The `get_resource_changes` function in the `sqlaudit.retrieval` module is used to retrieve changes made to a specific resource in the database. It allows you to filter changes by resource IDs, user IDs, and other criteria. This function is particularly useful for auditing purposes, as it enables you to track modifications made to your models over time.

#### Parameters

- `model_class`: *required* (e.g. `User`) The SQLAlchemy model class for which you want to retrieve changes.
- `session`: *required* The SQLAlchemy session to use for querying the database.
- `filter_resource_ids`: *required* A `ResourceIdType` or a list of `ResourceIdType` to filter the changes by resource IDs. This can be a single ID or a list of IDs. ResourceIdType can be a `str`, `int`, or `uuid.UUID`.
- `filter_fields`: *optional* A `str` or a list of `str` to filter the changes by specific fields. If not provided, all fields will be included.
- `filter_user_ids`: *optional* A `ResourceIdType` or a list of `ResourceIdType` to filter the changes by user IDs. If not provided, all user IDs will be included. ResourceIdType can be a `str`, `int`, or `uuid.UUID`.
- `filter_date_range`: *optional* `tuple[datetime | None, datetime | None]` to filter the changes by a date range. If not provided, all dates will be included.

### `sqlaudit.decorators.track_table()`  

The `track_table` decorator is used to enable auditing for a specific SQLAlchemy model. By applying this decorator to a model class, you can specify which fields should be tracked for changes, allowing SQLAudit to automatically record modifications made to those fields.

#### Parameters  

- `tracked_fields`: *required* A list of strings representing the names of the fields to be tracked for changes. These fields will be monitored for modifications, and any changes will be recorded in the audit table.
- `table_label`: *optional* A string representing the label for the table. This label is used in the audit table to identify the model being tracked. If not provided, the default label will be the name of 
the model class.
- `resource_id_field`: *optional* A string representing the name of the field that serves as the resource ID for the model. This field is used to uniquely identify instances of the model in the audit table. If not provided, the primary key field of the model will be used.
- `user_id_field`: *optional* A string representing the name of the field that stores the user ID of the user who made the change. This field is used to track which user made modifications to the model. If not provided, it will default to `config.user_model_user_id_field` from the global configuration.

### `set_audit_context()`

The `set_audit_context` function is used to set additional context for the audit entries. This also allows for overriding the default user ID gotten from the `get_user_id_callback` in the configuration.

#### Parameters

- `user_id`: *optional* A `ResourceIdType` representing the user ID of the user making the change. If not provided, the user ID will be retrieved using the `get_user_id_callback` from the configuration.
- `reason`: *optional* A string representing the reason for the change. This can be used to provide additional context for the audit entry.
- `impersonated_by`: *optional* A `ResourceIdType` representing the user ID of the user who is impersonating another user. This is useful for tracking changes made by users who are acting on behalf of others.

### Example Usage of `set_audit_context`

```python
from sqlaudit.context import set_audit_context

# Every operation performed after this will be audited with the specified context. 
set_audit_context(user_id=1, reason="Testing", impersonated_by=2)

new_customer = Customer(name="John Doe", email="jdoe@example.com")
db.add(new_customer)
```

### `AuditContextManager`

The `AuditContextManager` is a context manager that allows you to set the audit context for a specific block of code. This is useful when you want to temporarily override the default user ID or provide additional context for the audit entries. After the block is exited the context is reset to the previous state. 

#### Parameters

- `user_id`: *optional* A `ResourceIdType` representing the user ID of the user making the change. If not provided, the user ID will be retrieved using the `get_user_id_callback` from the configuration.
- `reason`: *optional* A string representing the reason for the change. This can be used to provide additional context for the audit entry.
- `impersonated_by`: *optional* A `ResourceIdType` representing the user ID of the user who is impersonating another user. This is useful for tracking changes made by users who are acting on behalf of others.

### Example Usage of `AuditContextManager`

```python
from sqlaudit.context import AuditContextManager
with AuditContextManager(user_id=1, reason="Testing", impersonated_by=2):
    # Every operation performed within this block will be audited with the specified context.
    # Perform operations that will be audited
    ... # Your code here

    db.flush()  # Ensure changes are flushed to the database

# State is reset back to the previous context 
```

### `Serializers`
The `Serializers` class provides automatic serialization and deserialization of values stored in the audit tables. Common Python types such as `int`, `float`, `str`, `bool`, `list`, `dict`, `datetime`, and `UUID` are supported out of the box. For custom types, you **must** register your own handlers using `Serializers.register_custom_handler()`, which will override the built-in behavior. This makes auditing simpler, ensures correct type restoration, and reduces the need for manual conversions.

#### Example Usage
```python
import json
import uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlaudit.serializers import Serializer, TypeHandler
from sqlaudit.decorators import track_table

# Example of a custom type
class CustomType:
    def __init__(self, value: int):
        self.value = value

    def __repr__(self):
        return f"CustomType(value={self.value})"

# Register a custom serializer and deserializer for the CustomType
Serializer.register_custom_handler(
    CustomType,
    TypeHandler(
        serialize=lambda v: json.dumps({"value": v.value}),
        deserialize=lambda v: CustomType(**json.loads(v))
    )
)

# Example SQLAlchemy base class
class Base(DeclarativeBase):
    pass

# Example of a model using the custom type with auditing enabled
@track_table(tracked_fields=["my_custom_type"])
class Foo(Base):
    __tablename__ = "foo"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    my_custom_type: Mapped[CustomType] = mapped_column()

# Example usage:
# foo_instance = Foo(my_custom_type=CustomType(42))
# db.add(foo_instance)
# db.commit()
```
