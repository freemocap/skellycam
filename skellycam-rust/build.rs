fn main() {
    let build_dir = r"C:\Users\jonma\code_repos\github\jonmatthis\openpnp-capture\build";
    let turbojpeg_lib_dir = format!("{build_dir}/libjpeg-turbo/install/lib");

    println!("cargo:rustc-link-search=native={build_dir}");
    println!("cargo:rustc-link-search=native={turbojpeg_lib_dir}");
    println!("cargo:rustc-link-lib=static=openpnp-capture");
    println!("cargo:rustc-link-lib=static=turbojpeg-static");
    println!("cargo:rustc-link-lib=ole32");
    println!("cargo:rustc-link-lib=oleaut32");
    println!("cargo:rustc-link-lib=strmiids");
}
