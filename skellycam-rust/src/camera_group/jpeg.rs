//! libjpeg-turbo (TurboJPEG API, statically linked by build.rs) for preview images and tracker pixels.
//!
//! One handle per call and thread: TurboJPEG handles are not shared between threads.

use std::ffi::{c_void, CStr};
use std::os::raw::{c_char, c_ulong};

use image::RgbImage;

type TjHandle = *mut c_void;
const TJPF_RGB: i32 = 0;
const TJPF_BGR: i32 = 1;
const TJSAMP_420: i32 = 2;
/// libjpeg-turbo decode option: nearest-neighbour chroma upsampling (faster; chroma edges differ).
pub const FAST_UPSAMPLE: i32 = 256;
/// libjpeg-turbo decode option: fast integer inverse DCT (faster; pixels differ slightly).
pub const FAST_DCT: i32 = 2048;

unsafe extern "C" {
    fn tjInitDecompress() -> TjHandle;
    fn tjInitCompress() -> TjHandle;
    fn tjDecompressHeader3(handle: TjHandle, jpeg_buf: *const u8, jpeg_size: c_ulong, width: *mut i32,
                           height: *mut i32, jpeg_subsamp: *mut i32, jpeg_colorspace: *mut i32) -> i32;
    fn tjDecompress2(handle: TjHandle, jpeg_buf: *const u8, jpeg_size: c_ulong, dst_buf: *mut u8, width: i32,
                     pitch: i32, height: i32, pixel_format: i32, flags: i32) -> i32;
    fn tjCompress2(handle: TjHandle, src_buf: *const u8, width: i32, pitch: i32, height: i32, pixel_format: i32,
                   jpeg_buf: *mut *mut u8, jpeg_size: *mut c_ulong, jpeg_subsamp: i32, jpeg_qual: i32,
                   flags: i32) -> i32;
    fn tjDestroy(handle: TjHandle) -> i32;
    fn tjFree(buffer: *mut u8);
    fn tjGetErrorStr2(handle: TjHandle) -> *const c_char;
}

/// A libjpeg-turbo handle; one per thread, destroyed on drop.
struct Turbo(TjHandle);

impl Turbo {
    fn new(handle: TjHandle, kind: &str) -> Result<Self, String> {
        if handle.is_null() { Err(format!("libjpeg-turbo could not create a {kind}")) } else { Ok(Self(handle)) }
    }

    fn error(&self) -> String {
        unsafe { CStr::from_ptr(tjGetErrorStr2(self.0)) }.to_string_lossy().into_owned()
    }
}

impl Drop for Turbo {
    fn drop(&mut self) {
        unsafe { tjDestroy(self.0) };
    }
}

fn read_header(turbo: &Turbo, jpeg: &[u8]) -> Result<(u32, u32), String> {
    let (mut width, mut height, mut subsampling, mut colorspace) = (0, 0, 0, 0);
    if unsafe { tjDecompressHeader3(turbo.0, jpeg.as_ptr(), jpeg.len() as c_ulong, &mut width, &mut height,
                                    &mut subsampling, &mut colorspace) } != 0 {
        return Err(format!("JPEG header: {}", turbo.error()));
    }
    Ok((width as u32, height as u32))
}

/// Decode at 1/`denominator` of the JPEG size using libjpeg-turbo's DCT scaling, as RGB.
pub(crate) fn decode_scaled(jpeg: &[u8], denominator: u32) -> Result<RgbImage, String> {
    let turbo = Turbo::new(unsafe { tjInitDecompress() }, "decompressor")?;
    let (width, height) = read_header(&turbo, jpeg)?;
    let (width, height) = (width.div_ceil(denominator), height.div_ceil(denominator));
    let mut pixels = vec![0u8; width as usize * height as usize * 3];
    // Asked for 1/denominator of the JPEG size, libjpeg-turbo decodes at exactly that DCT scale.
    if unsafe { tjDecompress2(turbo.0, jpeg.as_ptr(), jpeg.len() as c_ulong, pixels.as_mut_ptr(), width as i32,
                              (width * 3) as i32, height as i32, TJPF_RGB, 0) } != 0 {
        return Err(format!("JPEG decode: {}", turbo.error()));
    }
    RgbImage::from_raw(width, height, pixels).ok_or_else(|| "decoded image size mismatch".to_string())
}

/// Encode RGB pixels as JPEG with 4:2:0 chroma subsampling.
pub(crate) fn encode_jpeg(image: &RgbImage, quality: i32) -> Result<Vec<u8>, String> {
    let turbo = Turbo::new(unsafe { tjInitCompress() }, "compressor")?;
    let (mut buffer, mut size): (*mut u8, c_ulong) = (std::ptr::null_mut(), 0);
    let status = unsafe {
        tjCompress2(turbo.0, image.as_raw().as_ptr(), image.width() as i32, (image.width() * 3) as i32,
                    image.height() as i32, TJPF_RGB, &mut buffer, &mut size, TJSAMP_420, quality, 0)
    };
    let jpeg = if status == 0 && !buffer.is_null() {
        Ok(unsafe { std::slice::from_raw_parts(buffer, size as usize) }.to_vec())
    } else {
        Err(format!("JPEG encode: {}", turbo.error()))
    };
    if !buffer.is_null() {
        unsafe { tjFree(buffer) };
    }
    jpeg
}

/// Decode a camera JPEG at full size as BGR (OpenCV's channel order) into `dst`, which must hold exactly
/// `width * height * 3` bytes: the JPEG must have that size. `flags` 0 decodes exactly (libjpeg's accurate
/// IDCT and smooth upsampling, as OpenCV's decoder); `FAST_DCT` / `FAST_UPSAMPLE` trade exactness for speed.
pub(crate) fn decode_bgr_into(jpeg: &[u8], dst: &mut [u8], width: u32, height: u32, flags: i32) -> Result<(), String> {
    let turbo = Turbo::new(unsafe { tjInitDecompress() }, "decompressor")?;
    let size = read_header(&turbo, jpeg)?;
    if size != (width, height) || dst.len() != width as usize * height as usize * 3 {
        return Err(format!("JPEG is {}x{}, destination expects {width}x{height} ({} bytes)", size.0, size.1, dst.len()));
    }
    if unsafe { tjDecompress2(turbo.0, jpeg.as_ptr(), jpeg.len() as c_ulong, dst.as_mut_ptr(), width as i32,
                              (width * 3) as i32, height as i32, TJPF_BGR, flags) } != 0 {
        return Err(format!("JPEG decode: {}", turbo.error()));
    }
    Ok(())
}
