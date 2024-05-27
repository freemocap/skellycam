import pprint
from typing import Any, Dict

from pydantic import BaseModel
from pydantic.fields import FieldInfo


class DocPrintingBaseModel(BaseModel):
    def to_descriptive_dict(self, max_length: int = 100) -> Dict[str, Any]:
        """
        Creates a dictionary representation of the object values and includes a description of all fields of this object
        """
        descriptive_dict = {}
        descriptive_dict.update(self.model_dump())

        # truncate very long strings with internal elipses
        for key, value in descriptive_dict.items():
            if isinstance(value, str) and len(value) > max_length:
                start_str = value[: int(max_length / 2)]
                end_str = value[-int(max_length / 2):]
                descriptive_dict[key] = f"{start_str}...{end_str}"

        descriptive_dict["_field_descriptions"] = self.field_description_dict()
        return descriptive_dict

    def field_description_dict(self) -> Dict[str, str]:
        """
        Prints the description of all fields of this object in a dictionary {field_name: field_description}
        """
        # Instance variables
        instance_variables = {}
        output = {"class_name": f"{self.__class__.__name__}"}
        for field_name, field in self.__fields__.items():
            if field.description:
                instance_variables[field_name] = field.description
            else:
                instance_variables[field_name] = "No description provided"

        # Class variables
        class_variables = {}
        for field_name, value in self.__class__.__annotations__.items():
            if field_name not in self.__fields__:
                field_info = getattr(self.__class__, field_name, "No description provided")
                if isinstance(field_info, FieldInfo):
                    description_str = field_info.description or "No description provided"
                else:
                    description_str = "No description provided"
                class_variables[field_name] = {"field_description": description_str}

        if class_variables:
            output["class_variables"] = class_variables
        if instance_variables:
            output["instance_variables"] = instance_variables
        return output

    def docs(self) -> str:
        """
        Pretty prints a JSON-like representation of the object and its fields
        """
        return pprint.pformat(self.to_descriptive_dict(), indent=4)

    def __str__(self) -> str:
        return self.docs()
