const multiStepForm = document.querySelector('form[data-step-form]')
const formSteps = [...multiStepForm.querySelectorAll('fieldset[data-step]')]
let currentStep = formSteps.findIndex(step => step.classList.contains("active"))

if (currentStep < 0) {
  currentStep = 0
  formSteps[currentStep].classList.add('no-animation')  // <-- start bez animacji
  showCurrentStep()
}

multiStepForm.addEventListener("click", e => {
  let incrementor

  if (e.target.matches("[data-next]")) {
    incrementor = 1
  } else if (e.target.matches("[data-prev]")) {
    incrementor = -1
  }

  if (incrementor == null) return

  const inputs = [
    ...formSteps[currentStep].querySelectorAll("input"),
    ...formSteps[currentStep].querySelectorAll("select")
  ]

  const allValid = inputs.every(input => input.reportValidity())
  if (allValid) {
    // ✅ Teraz zmieniamy krok — dopiero teraz zdejmujemy `no-animation`
    formSteps[currentStep].classList.remove("no-animation")

    currentStep += incrementor
    showCurrentStep()
  }
})

formSteps.forEach(step => {
  step.addEventListener("animationend", e => {
    formSteps[currentStep].classList.remove("hide")
    e.target.classList.toggle("hide", !e.target.classList.contains("active"))
  })
})

function showCurrentStep() {
  formSteps.forEach((step, index) => {
    step.classList.toggle("active", index === currentStep)
  })
}
