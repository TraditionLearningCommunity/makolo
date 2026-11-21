document.addEventListener('DOMContentLoaded', () => {

  document.querySelectorAll('form[data-passport-visibility]').forEach((form) => {
    const choices = Array.from(form.querySelectorAll('input[name="audience"]'));
    const publicChoice = choices.find((input) => input.value === 'public');
    const person = form.querySelector('input[name="person_username"]');
    choices.forEach((input) => input.addEventListener('change', () => {
      if (!input.checked || !publicChoice) return;
      if (input === publicChoice) {
        choices.filter((other) => other !== publicChoice)
          .forEach((other) => { other.checked = false; });
      } else {
        publicChoice.checked = false;
      }
    }));
    if (person && publicChoice) {
      person.addEventListener('input', () => {
        if (person.value.trim()) publicChoice.checked = false;
      });
    }
  });

});
