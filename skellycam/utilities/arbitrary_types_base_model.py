from pydantic import BaseModel, ConfigDict


class ArbitraryTypesBaseModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )
