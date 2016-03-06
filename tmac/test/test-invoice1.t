.mso tmac.invoice
.reset_address
.start_address a 0 5c
One
Two
Three
.end_address
.start_address b 6c 5c
Four
Five
Six
Seven
.end_address
.restore
.S -2
.replay_address a Alpha
.replay_address b Beta
.S +2
Hello
