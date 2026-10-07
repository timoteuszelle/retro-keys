{
  lib,
  python3Packages,
  gtk4,
  libadwaita,
  adwaita-icon-theme,
  gobject-introspection,
  wrapGAppsHook4,
  udevCheckHook,
}:

python3Packages.buildPythonApplication {
  pname = "retro-keys";
  version = "0.1.0";
  pyproject = true;

  src = lib.cleanSourceWith {
    src = lib.cleanSource ../.;
    filter =
      path: type:
      let
        base = baseNameOf path;
      in
      base != "__pycache__" && !(lib.hasSuffix ".pyc" base);
  };

  build-system = with python3Packages; [ setuptools ];

  dependencies = with python3Packages; [ pygobject3 ];

  nativeBuildInputs = [
    gobject-introspection
    wrapGAppsHook4
    udevCheckHook
  ];

  buildInputs = [
    gtk4
    libadwaita
    adwaita-icon-theme
  ];

  dontWrapGApps = true;

  preFixup = ''
    makeWrapperArgs+=("''${gappsWrapperArgs[@]}")
  '';

  # The Python builder runs this as the install check, after the udev rule
  # is in $out. preInstallCheck is what udevCheckHook attaches to.
  checkPhase = ''
    runHook preInstallCheck
    PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v
    runHook postInstallCheck
  '';

  postInstall = ''
    install -Dm644 udev/60-retro-keys.rules $out/lib/udev/rules.d/60-retro-keys.rules
    install -Dm644 share/retro-keys.desktop $out/share/applications/online.meijokoen.RetroKeys.desktop
    install -Dm644 share/retro-keys.svg $out/share/icons/hicolor/scalable/apps/online.meijokoen.RetroKeys.svg
  '';

  doInstallCheck = true;

  meta = {
    description = "Program 8BitDo Retro Keyboard Super Buttons from Linux";
    license = lib.licenses.gpl3Plus;
    mainProgram = "retro-keys";
    platforms = lib.platforms.linux;
  };
}
