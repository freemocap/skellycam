import IconButton from "@mui/material/IconButton";
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTheme } from "@mui/material";
import {useAppDispatch} from "@/store/AppStateStore";
import {detectBrowserDevices} from "@/store/thunks/detect-cameras-thunks";

interface RefreshCamerasButtonProps {
    isLoading: boolean;
}

export const RefreshDetectedCamerasButton = ({ isLoading }: RefreshCamerasButtonProps) => {
    const theme = useTheme();
    const dispatch = useAppDispatch();

    const handleRefresh = (event: React.MouseEvent) => {
        event.stopPropagation();
        dispatch(detectBrowserDevices(true));
    };

    return (
        <IconButton
            onClick={handleRefresh}
            size="small"
            sx={{
                color: theme.palette.primary.contrastText,
                ml: 1,
                '&:hover': {
                    backgroundColor: 'rgba(255, 155, 255, 0.1)',
                }
            }}
            disabled={isLoading}
            title="Refresh available cameras"
        >
            <RefreshIcon fontSize="small" />
        </IconButton>
    );
};
