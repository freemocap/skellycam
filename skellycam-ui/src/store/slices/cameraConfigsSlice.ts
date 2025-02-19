import {CameraConfigSchema} from "@/models/SkellyCamAppStateSchema";
import {z} from "zod";
import {createEntityAdapter, createSlice} from "@reduxjs/toolkit";

type CameraConfig = z.infer<typeof CameraConfigSchema>;

const cameraAdapter = createEntityAdapter<CameraConfig>({
    selectId: (camera: any) => camera.camera_id.toString(),
});

export const cameraConfigsSlice = createSlice({
    name: 'cameraConfigs',
    initialState: cameraAdapter.getInitialState(),
    reducers: {
        camerasUpdateMany: cameraAdapter.updateMany,
        camerasSetAll: cameraAdapter.setAll,
        camerasUpdateOne: cameraAdapter.updateOne,
    }
});

export const {camerasUpdateMany, camerasSetAll, camerasUpdateOne} = cameraConfigsSlice.actions;
export default cameraConfigsSlice.reducer;
