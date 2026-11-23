// Progressive public-first defaults; submitted checkboxes are enforced by Django.
document.addEventListener('DOMContentLoaded', () => {
  const bind = (name, publicName, searchableName) => {
    const choices = [...document.querySelectorAll('input[name="' + name + '"]')];
    if (!choices.length) return;
    const collect = (field) => new Map(
      [...document.querySelectorAll('input[name="' + field + '"]')]
        .map((input) => [input.value, input])
    );
    const publicChoices = collect(publicName);
    const searchable = searchableName ? collect(searchableName) : new Map();
    const before = new Set(
      choices.filter((input) => input.checked).map((input) => input.value)
    );
    for (const input of choices) {
      input.addEventListener('change', () => {
        const publicInput = publicChoices.get(input.value);
        if (!input.checked) {
          if (publicInput) publicInput.checked = false;
          const searchInput = searchable.get(input.value);
          if (searchInput) searchInput.checked = false;
        } else if (!before.has(input.value) && publicInput) {
          publicInput.checked = true;
        }
      });
    }
    for (const option of [...publicChoices.values(), ...searchable.values()]) {
      option.addEventListener('change', () => {
        if (!option.checked) return;
        const input = choices.find((candidate) => candidate.value === option.value);
        if (input) input.checked = true;
      });
    }
  };
  bind('topics', 'public_topics');
  bind('kinds', 'public_kinds', 'searchable_kinds');
});
