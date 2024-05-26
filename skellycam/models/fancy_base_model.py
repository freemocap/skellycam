import pprint

from pydantic import Field

from skellycam.models.doc_printing_base_model import DocPrintingBaseModel
from skellycam.models.timestamping_base_model import TimestampingBaseModel
from skellycam.utilities.wait_functions import wait_10ms


class FancyBaseModel(TimestampingBaseModel, DocPrintingBaseModel):
    pass


if __name__ == "__main__":
    # Example usage
    class MyFancyModel(FancyBaseModel):
        attribute: int = Field(description="An example attribute")

        def example_method(self):
            wait_10ms()
            print("Method called!")

    # Testing the updated implementation
    model = MyFancyModel(attribute=10)
    model.attribute = 20
    model.example_method()
    model.example_method()
    del model.attribute

    print("Timestamps:")
    print(model.get_timestamps())

    print("Docs:")
    print(model.docs())

    print("Field Descriptions:")
    print(pprint.pformat(model.field_description_dict(), indent=4))

    print("Descriptive Dict:")
    print(pprint.pformat(model.to_descriptive_dict(), indent=4))
