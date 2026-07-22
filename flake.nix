{
  description = "A simple python hello world project with Nix flakes";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      # Supported systems for multiplatform support
      supportedSystems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];

      # Helper function to generate an attrset '{ x86_64-linux = ... }'
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;

      # Nixpkgs instantiated for each system
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgsFor.${system};
        in
        {
          default = pkgs.mkShell {
            buildInputs = [
              (pkgs.python312.withPackages (ps: with ps; [
                (telethon.overridePythonAttrs (old: { doCheck = false; }))
                python-dotenv
                questionary
              ]))
            ];

            shellHook = ''
              echo "Welcome to the Python Hello World dev shell!"
              python3 --version
            '';
          };
        });
    };
}
