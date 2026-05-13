fn main() {
    let lib_path = r"C:\Users\jonma\code_repos\github\jonmatthis\openpnp-capture\build";
    println!("cargo:rustc-link-search=native={}", lib_path);
    println!("cargo:rustc-link-lib=static=openpnp-capture");
    println!("cargo:rustc-link-lib=ole32");
    println!("cargo:rustc-link-lib=oleaut32");
    println!("cargo:rustc-link-lib=strmiids");
}
