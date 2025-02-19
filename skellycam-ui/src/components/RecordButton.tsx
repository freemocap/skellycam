import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectIsRecording} from '@/store/slices/appState/selectors';
import {startRecording, stopRecording} from '@/store/thunks/recordingThunks';
import {Button} from '@mui/material';

export const RecordButton = () => {
    const isRecording = useAppSelector(selectIsRecording);
    const dispatch = useAppDispatch();

    return (
        <Button
            onClick={() => dispatch(isRecording ? startRecording() : stopRecording())}
            disabled={isRecording}
            sx={{
                backgroundColor: isRecording ? 'red' : 'blue',
                color: 'fafafa',
                fontSize: 24,
                padding: 16,
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
            }}
        >
            {isRecording ? 'Recording...' : 'Start Recording'}
        </Button>
    );
};
