(() => {
  const startDate = document.querySelector("#start_date");
  const endDate = document.querySelector("#end_date");
  const amount = document.querySelector("#amount");
  if (!startDate || !endDate || !amount) return;

  const millisecondsPerDay = 24 * 60 * 60 * 1000;
  const minimumDays = Number(endDate.dataset.minimumDays);

  const parseDate = (value) => {
    const parts = value.split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) return null;
    return Date.UTC(parts[0], parts[1] - 1, parts[2]);
  };

  const updateAmount = () => {
    const start = parseDate(startDate.value);
    const end = parseDate(endDate.value);
    if (start !== null) {
      const earliestEnd = new Date(
        start + (minimumDays - 1) * millisecondsPerDay,
      ).toISOString().slice(0, 10);
      endDate.min = earliestEnd;
      if (end !== null && end < start + (minimumDays - 1) * millisecondsPerDay) {
        endDate.value = earliestEnd;
      }
    }

    const adjustedEnd = parseDate(endDate.value);
    if (start === null || adjustedEnd === null || adjustedEnd <= start) {
      amount.value = "";
      return;
    }

    const inclusiveDays = Math.round(
      (adjustedEnd - start) / millisecondsPerDay,
    ) + 1;
    amount.value = (inclusiveDays * 3).toFixed(2);
  };

  startDate.addEventListener("input", updateAmount);
  endDate.addEventListener("input", updateAmount);
  updateAmount();
})();
