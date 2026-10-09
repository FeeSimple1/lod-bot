# Winter Quarters card choice audit

Cards 102 (War on the Frontier) and 103 (Severe Winter), in `Reference Documents/card reference full.txt`, instruct the Patriot or Indian faction ahead in its second victory condition to remove one of its own Forts or Villages during Reset. Manual §5.1 assigns the details of an action to the faction specified to perform it.

Before this correction, `_lose_fort_or_village` always selected a space with the Non-player Random Spaces procedure, including when the affected faction was human. The correction lets the affected human select from spaces containing its appropriate piece. Bot selection remains the Random Spaces procedure. The trigger, amount, piece type, destination, and Reset timing remain governed by the existing card implementation.
