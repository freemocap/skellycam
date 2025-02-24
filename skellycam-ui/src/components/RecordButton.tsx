import React from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectIsRecording} from '@/store/slices/appState/selectors';
import {startRecording, stopRecording} from '@/store/thunks/recordingThunks';
import {Button} from '@mui/material';

export const RecordButton: React.FC = () => {
  const isRecording = useAppSelector(selectIsRecording);
  const dispatch = useAppDispatch();

  const handleButtonClick = () => {
    if (isRecording) {
      dispatch(stopRecording());
    } else {
      dispatch(startRecording());
    }
  };

  return (
    <Button
      onClick={handleButtonClick}
      sx={{
        backgroundColor: isRecording ? 'red' : 'blue',
        color: '#fafafa',
        fontSize: '16px',
        padding: '10px 20px',
        borderRadius: '8px',
      }}
    >
      {isRecording ? 'Stop Recording' : 'Start Recording'}
    </Button>
  );
};