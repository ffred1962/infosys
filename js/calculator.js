/**
 * Валидация и отправка формы калькулятора на /api/plus
 */

const form = document.getElementById("calculatorForm");
const inputA = document.getElementById("inputA");
const inputB = document.getElementById("inputB");
const errorA = document.getElementById("errorA");
const errorB = document.getElementById("errorB");
const resultContainer = document.getElementById("resultContainer");
const errorContainer = document.getElementById("errorContainer");
const resultValue = document.getElementById("resultValue");
const errorMessage = document.getElementById("errorMessage");

/**
 * Валидирует введённое значение (число и не пусто)
 * @param {HTMLInputElement} input - поле ввода
 * @param {HTMLElement} errorElement - элемент для вывода ошибки
 * @returns {boolean} валидно ли значение
 */
function validateInput(input, errorElement) {
  const value = input.value.trim();

  if (value === "") {
    errorElement.textContent = "Поле не может быть пустым";
    input.classList.add("is-invalid");
    return false;
  }

  const num = parseFloat(value);
  if (isNaN(num)) {
    errorElement.textContent = "Введите корректное число";
    input.classList.add("is-invalid");
    return false;
  }

  if (!isFinite(num)) {
    errorElement.textContent = "Число слишком большое";
    input.classList.add("is-invalid");
    return false;
  }

  errorElement.textContent = "";
  input.classList.remove("is-invalid");
  return true;
}

/**
 * Обработчик подтверждения формы
 */
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Очистка ошибок
  errorA.textContent = "";
  errorB.textContent = "";
  inputA.classList.remove("is-invalid");
  inputB.classList.remove("is-invalid");
  resultContainer.classList.add("d-none");
  errorContainer.classList.add("d-none");

  // Валидация на клиенте
  const isAValid = validateInput(inputA, errorA);
  const isBValid = validateInput(inputB, errorB);

  if (!isAValid || !isBValid) {
    return;
  }

  // Подготовка данных и отправка на сервер
  const a = parseFloat(inputA.value);
  const b = parseFloat(inputB.value);

  try {
    const response = await fetch("/api/plus", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ a, b }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(
        errorData.detail || `Ошибка сервера: ${response.statusText}`
      );
    }

    const data = await response.json();
    resultValue.textContent = data.result;
    resultContainer.classList.remove("d-none");
  } catch (error) {
    errorMessage.textContent =
      error.message || "Не удалось выполнить расчет";
    errorContainer.classList.remove("d-none");
  }
});

/**
 * Очистка ошибок при редактировании поля
 */
inputA.addEventListener("input", () => {
  errorA.textContent = "";
  inputA.classList.remove("is-invalid");
});

inputB.addEventListener("input", () => {
  errorB.textContent = "";
  inputB.classList.remove("is-invalid");
});
