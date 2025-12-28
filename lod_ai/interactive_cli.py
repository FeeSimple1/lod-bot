#!/usr/bin/env python3
"""
interactive_cli.py — Command-line interface for starting and playing Liberty or Death.
Prompts the user to select number of human players (0–3), which factions they control,
and which scenario (1775/Long, 1776/Medium, 1778/Short).  Then runs the game loop,
prompting human players for legal actions each turn and invoking the game engine
for all actions.  All turns (including bot moves) pause for a keypress.
"""
import sys
from engine import Engine
from dispatcher import Dispatcher
import rules_consts as RC


def main():
    # Map input numbers to faction names and scenario names
    factions = {
        1: RC.PATRIOTS,
        2: RC.BRITISH,
        3: RC.FRENCH,
        4: RC.INDIANS
    }
    scenario_options = {
        1: ("1775", "Long"),
        2: ("1776", "Medium"),
        3: ("1778", "Short")
    }

    # Setup loop: get valid input and confirm
    while True:
        try:
            num_humans = int(input("Enter number of human players (0-3): ").strip())
        except ValueError:
            print("Invalid number. Please enter an integer 0-3.")
            continue
        if num_humans < 0 or num_humans > 3:
            print("Must be between 0 and 3.")
            continue

        human_factions = []
        if num_humans > 0:
            print("Select which factions are human-controlled (choose {}):".format(num_humans))
            for key, name in factions.items():
                print(f"  {key}. {name.capitalize()}")
            choices = input(f"Enter {num_humans} numbers separated by spaces: ").split()
            try:
                chosen = [int(x) for x in choices]
            except ValueError:
                print("Invalid selection. Please enter numbers only.")
                continue
            if len(chosen) != num_humans or any(x not in factions for x in chosen):
                print("You must choose exactly {} distinct factions by number.".format(num_humans))
                continue
            human_factions = [factions[x] for x in chosen]
        else:
            human_factions = []

        # Choose scenario
        print("Select a scenario:")
        for num, (year, label) in scenario_options.items():
            print(f"  {num}. {year} ({label} scenario)")
        try:
            scen_choice = int(input("Enter scenario number: ").strip())
        except ValueError:
            print("Invalid scenario number.")
            continue
        if scen_choice not in scenario_options:
            print("Scenario number must be 1, 2, or 3.")
            continue

        # Summary and confirmation
        year, label = scenario_options[scen_choice]
        print("\nConfiguration:")
        print(f"  Human players: {num_humans}")
        print(f"  Human factions: {', '.join(human_factions) if human_factions else 'None'}")
        print(f"  Scenario: {year} ({label})")
        confirm = input("Confirm? (Y/N): ").strip().lower()
        if confirm == 'y':
            break  # proceed with game
        else:
            print("Restarting setup...\n")

    # Initialize game engine and dispatcher
    game = Engine()
    game.setup_scenario(year)  # configure pieces and deck for selected scenario
    dispatcher = Dispatcher(game)
    # Inform engine/dispatcher which factions are human-controlled
    game.set_human_factions(human_factions)
    dispatcher.set_human_factions(human_factions)

    print("\nStarting game...\n")
    # Main game loop: play cards until game end
    while True:
        # Draw or peek at next event card
        card = game.draw_card()
        if card is None:
            print("No more cards in deck. Game over.")
            break
        print(f"--- Now playing card: {card.name} ---")

        # Determine eligible factions on this card, in card-symbol order
        card_factions = card.symbols  # left-to-right symbol list (e.g. [PATRIOTS, BRITISH])
        eligible = [f for f in card_factions if game.is_eligible(f)]
        if not eligible:
            print("No eligible factions this turn.")
            # Possibly continue to next card
            continue
        first = eligible[0]
        second = eligible[1] if len(eligible) > 1 else None

        # -------- FIRST ELIGIBLE ACTION --------
        first_action = None
        if game.is_human_faction(first):
            # Prompt human for first eligible action
            print(f\"\nFirst eligible: {first.capitalize()}\")
            while True:
                # List allowed options for first eligible (pass, event, command)
                opts = []
                opts.append(\"P) Pass\")
                opts.append(\"E) Play Event\")
                opts.append(\"C) Command (with optional Special)\")
                print(\"Choose action: \" + \" | \".join(opts))
                choice = input(\"Enter P, E, or C: \").strip().upper()
                if choice == 'P':
                    first_action = 'pass'
                    break
                elif choice == 'E':
                    first_action = 'event'
                    break
                elif choice == 'C':
                    first_action = 'command'
                    break
                else:
                    print(\"Invalid choice. Please enter P, E, or C.\")
            # Execute the chosen action
            if first_action == 'pass':
                gain = 2 if first in [RC.BRITISH, RC.FRENCH] else 1
                game.add_resources(first, gain)
                print(f\"{first.capitalize()} passes and gains {gain} resources.\")
                input(\"Press Enter to continue...\")
                # Treat second as new first if it exists
                if second:
                    # Reset action to treat second as if first
                    first = second
                    second = None
                else:
                    # No second, end of this card
                    first_action = None
                # Proceed to second (now in the role of first)
            elif first_action == 'event':
                print(f\"{first.capitalize()} plays the Event on the card.\")
                dispatcher.execute_event(first, card)  # use dispatcher to apply event
                input(\"Press Enter to continue...\")
                # Now second (if any) will be allowed a Command
            elif first_action == 'command':
                # Prompt for command and optional special (details abstracted)
                cmd = input(\"Enter Command name for {}: \".format(first)).strip()
                special = input(\"Enter Special Activity name (or leave blank): \").strip()
                print(f\"{first.capitalize()} executes Command '{cmd}'\" +
                      (f\" with Special '{special}'.\" if special else \".\"))
                dispatcher.execute_command(first, cmd, special or None, limited=False)
                input(\"Press Enter to continue...\")
        else:
            # Bot logic for first eligible
            print(f\"\nFirst eligible (bot): {first.capitalize()}\")
            dispatcher.execute_bot_turn(first, card)
            first_action = dispatcher.last_action(first)
            input(\"Press Enter to continue...\")

        # -------- SECOND ELIGIBLE ACTION (if applicable) --------
        if first_action != 'pass' and second:
            # Determine allowed actions for second based on first_action
            print(f\"\nSecond eligible: {second.capitalize()}\")
            if game.is_human_faction(second):
                # Build options list for second
                second_opts = []
                second_opts.append(\"P) Pass\")
                if first_action == 'event':
                    second_opts.append(\"C) Command (with optional Special)\")
                elif first_action == 'command':
                    # First did command with unknown special; ask if special was provided above
                    second_opts.append(\"L) Limited Command\")
                    if special:
                        second_opts.append(\"E) Play Event\")
                elif first_action is None:
                    # Case: first passed and second is now acting as first
                    second_opts.append(\"E) Play Event\")
                    second_opts.append(\"C) Command (with optional Special)\")
                # Prompt choice
                while True:
                    print(\"Choose action: \" + \" | \".join(second_opts))
                    choice = input(\"Enter your choice: \").strip().upper()
                    if choice == 'P':
                        action2 = 'pass'
                        break
                    elif choice == 'E' and 'E) Play Event' in second_opts:
                        action2 = 'event'
                        break
                    elif choice == 'C' and 'C) Command' in second_opts:
                        action2 = 'command'
                        break
                    elif choice == 'L' and 'L) Limited Command' in second_opts:
                        action2 = 'limited'
                        break
                    else:
                        print(\"Invalid choice. Please select one of the options shown.\")
                # Execute second's action
                if action2 == 'pass':
                    gain2 = 2 if second in [RC.BRITISH, RC.FRENCH] else 1
                    game.add_resources(second, gain2)
                    print(f\"{second.capitalize()} passes and gains {gain2} resources.\")
                elif action2 == 'event':
                    print(f\"{second.capitalize()} plays the Event on the card.\")
                    dispatcher.execute_event(second, card)
                elif action2 == 'command':
                    cmd2 = input(\"Enter Command name for {}: \".format(second)).strip()
                    special2 = input(\"Enter Special Activity name (or leave blank): \").strip()
                    print(f\"{second.capitalize()} executes Command '{cmd2}'\" +
                          (f\" with Special '{special2}'.\" if special2 else \".\"))
                    dispatcher.execute_command(second, cmd2, special2 or None, limited=False)
                elif action2 == 'limited':
                    cmd2 = input(\"Enter Limited Command for {}: \".format(second)).strip()
                    print(f\"{second.capitalize()} executes Limited Command '{cmd2}'.\")
                    dispatcher.execute_command(second, cmd2, None, limited=True)
                input(\"Press Enter to continue...\")
            else:
                # Bot logic for second eligible
                dispatcher.execute_bot_turn(second, card, first_action)
                input(\"Press Enter to continue...\")

        # After both eligible factions have acted (or passed), check for victory or next card
        if game.is_victory():
            print(f\"Game ends: {game.winner} wins!\")
            break

    print(\"\\nGame over. Thanks for playing!\")


if __name__ == \"__main__\":
    main()
