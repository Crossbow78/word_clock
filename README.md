# Word Clock Project
## Overview

This is a controller for the amazing Word Clock 3D print by Jan Romaniak:
https://makerworld.com/en/models/686196#profileId-614840

## Features

### Visualization modes

The following modes are available (thanks Claude AI):
* Group: Current
    * Word clock - Spells out current time, main intent of 3D print, displayed on startup
    * Weather - Shows local weather as status icon and temperature
    * Presence - Shows the presence of family members by pinging their mobile phones

* Group: Animations
    * Balls - bouncing colored balls animation using subpixel precision
    * Fire - yellow-red fire animation, for those cold winter days
    * Flowfield - Streaks of colored smoke, bit abstract
    * Plasma - Bright plasma colored animation
    * Ripple - Colored water ripples
    * Lavalamp - Moving colored blobs fading into each other, using subpixel precision
    * Spiral - Like spinning fan blades
    * Flags - Rotates through several country flags
    * Matrix - Green falling letters animation from The Matrix movie
    * Sand - Falling sand grains, forming a growing pile
    * Life - Conway's game of life
    * Lightning - Simulates lightning bolts

* Group: Games
    * Tetris - Classic falling bricks game, played by AI
    * Snake - Classic moving snake that must capture fruits which will grow its tail, played by AI
    * Chess - Color-coded chess board, played by AI
    * Reversi - Turn the stones into your color, also known as Othello
    * Connect Four - Try to get four stones in a row
    * Lights Out - Turn all the lights off by toggling neighboring tiles

### Hardware button

There is support for a hardware button to select different modes:
   * Long-press to cycle between groups
   * Single-press to cycle between modes within group
   * Double-press to (de)activate automatic cycling between modes

### Web user interface

The current mode, auto-cycling and pixel brightness can be controlled via a mobile-friendly web UI
that can be accessed at port 8000 of the raspberry pi, eg. http://{pi-zero-ip-address}:8000/