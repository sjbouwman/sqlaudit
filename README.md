# SQLAudit

`SQLAudit` is a SQLAlchemy extension that provides an easy way to track changes to your database models. It automatically creates an audit trail of changes made to your models, including the user who made the change, the timestamp of the change.

It is designed to work with SQLAlchemy's ORM and provides a simple way to track changes to your models without having to write custom code for each model. SQLAudit only requires you to decorate your models with the `@track_table` decorator, and it will automatically track changes to the specified fields.

```python
@track_table(tracked_fields=["name", "email", "user_id"])
class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
```

## Notice  

This project is in its early stages and is not yet ready for production use.

## Quick start

To get started with `SQLAudit`, you need to install it using pip:

```bash
pip install sqlaudit
```

Follow the steps below to set up and use `SQLAudit` in your SQLAlchemy application.

This short guide demonstrates how to setup and use `SQLAudit`. 

### Step 1: Define your Base and User model

`SQLAudit` requires access to a `SQAlchemy` `Base` class. We will also define a `User` class which will be used to identify who made which change, and a `session factory` to create sessions.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Create an in-memory SQLite database
DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a database session for an in-memory SQLite DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[string] = mapped_column()


```

### Step 2: Configure SQLAudit  

Set the global configuration using `set_audit_config()`.

```python
from sqlaudit import set_audit_config
from utils.db import engine, get_db  # your db utils

set_audit_config(
    engine=engine, #  SQLAlchemy engine
    Base=Base, # SQLAlchemy Base class defined in Step 1
    session_factory=get_db, # function to get a SQLAlchemy session
    default_user_id_field="user_id", # field in User model to identify user
    user_model=User, # User model defined in Step 1
    user_id_field="user_id", # field in User model to identify user
)
```

### Step 3: Add SQLAudit to your models  

To enable auditing for your models use the `@track_table` decorator. This decorator will automatically track changes to the model and store them in the audit table. There are various options you can pass to the decorator to customize the behavior. The most basic usage only requires a list of strings representing the columns you want to track.

```python
from sqlaudit import track_table
from sqlalchemy import Integer, String

@track_table(tracked_fields=["name", "email", "user_id"])
class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
```

#### Step 4: Register the SQLAudit hooks

SQLAudit uses two SQLAlchemy events to track changes: `before_flush` and `after_flush`. You need to register these hooks to enable auditing.

We will be doing this in a `startup` function that will be called when the application starts.

```python
if __name__ == "__main__":
    Base.metadata.create_all(engine)

    register_audit_hooks()
```

### Step 5: Use the session to make changes

Now you can use the session to make changes to your models. SQLAudit will automatically track these changes and store them in the audit table.

```python
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

    # We check if the customer is in the database
    customer = (
        session.query(Customer)
        .filter_by(customer_id=new_customer.customer_id)
        .first()
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
        filter_user_ids=str(user.user_id),
    )

    for change in changes:
        print(change)

```
