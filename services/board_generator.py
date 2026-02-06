import random


def validate_word_count(words, board_size, card_count, word_mode):
    cells = board_size * board_size - (1 if board_size == 5 else 0)

    if len(words) < cells:
        return (
            False,
            f"Need at least {cells} words for a {board_size}x{board_size} board, "
            f"but only have {len(words)}.",
        )

    if word_mode == "different_per_board" and len(words) < cells + 5:
        recommended = min(cells * 2, cells + card_count * 3)
        return (
            False,
            f"For boards with different words, recommend at least {recommended} words. "
            f"You have {len(words)}. Add more words or switch to 'Same words' mode.",
        )

    return True, "OK"


def generate_boards(words, board_size, card_count, word_mode, custom_words=None):
    cells_needed = board_size * board_size - (1 if board_size == 5 else 0)
    boards = []
    seen = set()

    # Custom words are guaranteed on every card; fill remaining slots randomly
    guaranteed = [w for w in (custom_words or []) if w in words]
    remaining_pool = [w for w in words if w not in guaranteed]

    for _ in range(card_count):
        attempts = 0
        while attempts < 100:
            fill_needed = cells_needed - len(guaranteed)
            if word_mode == "same_shuffled":
                filler = random.sample(remaining_pool, fill_needed)
            else:
                filler = random.sample(remaining_pool, min(fill_needed, len(remaining_pool)))
            card_words = guaranteed + filler
            random.shuffle(card_words)

            board_key = tuple(card_words)
            if board_key not in seen or card_count > _factorial_limit(cells_needed):
                seen.add(board_key)
                break
            attempts += 1

        grid = _build_grid(card_words, board_size)
        boards.append(grid)

    return boards


def _build_grid(words_for_card, board_size):
    grid = []
    idx = 0
    for row in range(board_size):
        row_cells = []
        for col in range(board_size):
            if board_size == 5 and row == 2 and col == 2:
                row_cells.append("FREE")
            else:
                row_cells.append(words_for_card[idx])
                idx += 1
        grid.append(row_cells)
    return grid


def _factorial_limit(n):
    """Return a reasonable upper limit to avoid checking too many permutations."""
    result = 1
    for i in range(1, min(n + 1, 13)):
        result *= i
    return result
