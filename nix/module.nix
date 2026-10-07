# Installs Retro Keys and lets the logged-in user open the keyboard's
# config interface. The udev rule does not unbind usbhid.
{ config, lib, ... }:
let
  cfg = config.programs.retro-keys;
in
{
  options.programs.retro-keys = {
    enable = lib.mkEnableOption "Retro Keys, a configurator for the 8BitDo Retro Keyboard";
    package = lib.mkOption {
      type = lib.types.package;
      description = "Package that provides retro-keys and its udev rule.";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ cfg.package ];
    services.udev.packages = [ cfg.package ];
  };
}
