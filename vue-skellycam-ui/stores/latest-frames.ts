export const useLatestFrames = defineStore('latestFrames', () => {
    const latestMultiFramePayload = ref<{ jpeg_images?: { [key: string]: string } } | null>(null);

    const latestImages = computed(() => latestMultiFramePayload.value?.jpeg_images || {})

    const setLatestFrames = (newFrames: object) => {
        latestMultiFramePayload.value = newFrames;
    }

    return {
        latestImages,
        setLatestFrames
    }
})
