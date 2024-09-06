# peerstream
Experimental HLS based video sharing application

This is just an old side project I was working on a few years ago, that leverages HLS in order to serve up a video stream in small fragments and pass them around between a network of peer nodes.

There are two types of node: a player or a seeder. The latter is a headless version of the former, so if you want to play a video you can only do it locally from your seeder. 

In principle it works but the question is whether it'll ever be fast enough and if so, how many seeders do you need to support n players?
