fn main() {
    // Hardcoded path to forked openpnp-capture build directory.
    // FIXME: replace with a proper build script that compiles the C library
    //        from source (using cc/cmake crates) or a submodule path.
    let lib_path = r"C:\Users\jonma\code_repos\github\jonmatthis\openpnp-capture\build";
    println!("cargo:rustc-link-search=native={}", lib_path);
    println!("cargo:rustc-link-lib=static=openpnp-capture");
    // DirectShow / COM dependencies — inferred from linker errors:
    //   ole32    → CoInitializeEx, CoCreateInstance, CoTaskMemFree, etc.
    //   oleaut32 → VariantInit, VariantClear
    //   strmiids → DirectShow CLSID/IID definitions
    // These are implicit when building with MSVC's C++ project system;
    // explicit when linking from Rust.
    println!("cargo:rustc-link-lib=ole32");
    println!("cargo:rustc-link-lib=oleaut32");
    println!("cargo:rustc-link-lib=strmiids");
}
