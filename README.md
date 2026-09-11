# liquidWeb

> [!WARNING]
> In the very unlikely condition that something happens I need to state that I'm not responsible for any damage to your equipment. If anything get stuck your best option is to turn off your PC and disconnect it from power for a minute or two before restarting it. I myself have not had any issues while using this program.

A simple NZXT CAM imitation based on code of [AIOLCDUnchained](https://github.com/brokenmass/AIOLCDUnchained) by [brokenmass](https://github.com/brokenmass).

This program allows you to have the replica of NZXT CAM's feature called "Web Integration" that makes it possible to create your own web based integrations for the little LCD on the AIO's pump but on Linux!

It also has the support of very primitive fan curves with the usage of cpu temperature (editable under /var/lib/liquidWeb/curves.json).

Generally the program is very rough around the edges but it does what I need.

## Installation

Grab the latest .rpm and install it. Everything should be configured automatically and ready for you.

## Configuration

Run
```console
# liquidWeb-configure-integration
```
to start the integration in configuration mode (this means that the `kraken` parameter is set to 1).

If you want to configure the parameters of the different parts of the programs simply edit their corresponding systemd services.

## Device support
As per the [AIOLCDUnchained README](https://github.com/brokenmass/AIOLCDUnchained?tab=readme-ov-file#full-app-roadmap) the supported devices are NZXT Kraken 2023 Elite and NZXT Kraken Z3.

Tested on real hardware on Fedora 44