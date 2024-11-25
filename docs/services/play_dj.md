# Play DJ

`spotcast.play_dj`

## Description

Start the playback of the DJ playlist on a specified device

## Example service call

```yaml
action: spotcast.play_dj
data:
    media_player:
        entity_id: media_player.foo
    spotify_account: 01JDG07KSBTYWZGJSBJ1EW6XEF
    data:
        repeat: context
```

## Fields

### Media Player

Let the user select a compatible device on which to start the playback. **_Must be a single device_**.

### Spotify Account

*Optional*

The `entry_id` of the account to use for Spotcast. If empty, the default Spotcast account is used.

### Data

*Optional*

Set of additional settings to apply when starting the playback. The available options are:

| Option   | type                 | default | description                                                                                                    |
| :---:    | :---:                | :---:   | :---                                                                                                           |
| `volume` | `int`, `range 0-100` | `null`  | The percentage (as an integer of the percentage value) to start plaback at. Volume is kept unchanged if `null` |