import { z } from 'zod';

export const CurrentFramerateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    frame_duration_max: z.number(),
    frame_duration_min: z.number(),
    frame_duration_mean: z.number(),
    frame_duration_stddev: z.number(),
    frame_duration_median: z.number(),
    frame_duration_coefficient_of_variation: z.number(),
    calculation_window_size: z.number(),
    framerate_source: z.string(),
});

export type CurrentFramerate = z.infer<typeof CurrentFramerateSchema>;
