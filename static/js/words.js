document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('wordContainer');
    const newWordInput = document.getElementById('newWordInput');
    const addWordBtn = document.getElementById('addWordBtn');
    const selectAllBtn = document.getElementById('selectAllBtn');
    const deselectAllBtn = document.getElementById('deselectAllBtn');
    const wordsForm = document.getElementById('wordsForm');
    const selectedWordsInput = document.getElementById('selectedWordsInput');
    const wordCountText = document.getElementById('wordCountText');
    const wordCountAlert = document.getElementById('wordCountAlert');

    updateWordCount();

    // Toggle word on click
    container.addEventListener('click', function(e) {
        const chip = e.target.closest('.word-chip');
        if (!chip) return;

        if (chip.classList.contains('selected')) {
            chip.classList.remove('selected');
            chip.classList.add('deselected');
        } else {
            chip.classList.remove('deselected');
            chip.classList.add('selected');
        }
        updateWordCount();
    });

    // Add new word
    function addWord() {
        const word = newWordInput.value.trim().toLowerCase();
        if (!word) return;

        // Check for duplicates
        const existing = container.querySelectorAll('.word-chip');
        for (const chip of existing) {
            if (chip.dataset.word === word) {
                chip.classList.remove('deselected');
                chip.classList.add('selected');
                newWordInput.value = '';
                updateWordCount();
                return;
            }
        }

        const chip = document.createElement('span');
        chip.className = 'word-chip selected';
        chip.dataset.word = word;
        chip.dataset.source = 'custom';
        chip.textContent = word;
        container.appendChild(chip);
        newWordInput.value = '';
        updateWordCount();
    }

    addWordBtn.addEventListener('click', addWord);
    newWordInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addWord();
        }
    });

    // Select all
    selectAllBtn.addEventListener('click', function() {
        container.querySelectorAll('.word-chip').forEach(chip => {
            chip.classList.remove('deselected');
            chip.classList.add('selected');
        });
        updateWordCount();
    });

    // Deselect all
    deselectAllBtn.addEventListener('click', function() {
        container.querySelectorAll('.word-chip').forEach(chip => {
            chip.classList.remove('selected');
            chip.classList.add('deselected');
        });
        updateWordCount();
    });

    // Update word count display
    function updateWordCount() {
        const selected = container.querySelectorAll('.word-chip.selected');
        const total = container.querySelectorAll('.word-chip');
        const count = selected.length;

        let msg = `${count} of ${total.length} words selected. `;
        if (count >= 24) {
            msg += 'Enough for 4x4 or 5x5 boards.';
            wordCountAlert.className = 'alert alert-success d-flex align-items-center mb-3';
        } else if (count >= 16) {
            msg += 'Enough for a 4x4 board. Need 24+ for 5x5.';
            wordCountAlert.className = 'alert alert-info d-flex align-items-center mb-3';
        } else {
            msg += `Need at least 16 words for a 4x4 board.`;
            wordCountAlert.className = 'alert alert-warning d-flex align-items-center mb-3';
        }
        wordCountText.textContent = msg;
    }

    // On form submit, collect selected words
    wordsForm.addEventListener('submit', function() {
        const selected = container.querySelectorAll('.word-chip.selected');
        const words = Array.from(selected).map(chip => chip.dataset.word);
        selectedWordsInput.value = JSON.stringify(words);
    });
});
