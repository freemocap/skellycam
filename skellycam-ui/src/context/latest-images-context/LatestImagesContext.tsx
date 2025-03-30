import {JpegImages, useLatestImages} from "./useLatestImages";
import {createContext, useContext} from "react";

interface  LatestImagesContextProps {
    latestImageUrls: { [cameraId: string]: string };
    setLatestImages: (latestImages: JpegImages) => void;
}

interface LatestImagesProviderProps {
    children: React.ReactNode;
}

const LatestImagesContext = createContext<LatestImagesContextProps | undefined>(undefined);

export const LatestImagesContextProvider: React.FC<LatestImagesProviderProps> = ({children}) => {
    const {setLatestImages, latestImageUrls} = useLatestImages()

    return (
        <LatestImagesContext.Provider value={{latestImageUrls, setLatestImages}}>
            {children}
        </LatestImagesContext.Provider>
    )
}

export const useLatestImagesContext = () => {
    const context = useContext(LatestImagesContext);
    if (!context) {
        throw new Error('useLatestImagesContext must be used within a LatestImagesProvider');
    }
    return context;
};
