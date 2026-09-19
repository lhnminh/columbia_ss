(() => {
  const replaceDirectory = async (url, updateHistory) => {
    const current = document.querySelector("#browse");
    if (!current) return;

    const scrollPosition = window.scrollY;
    current.setAttribute("aria-busy", "true");

    try {
      const requestUrl = new URL(url, window.location.href);
      requestUrl.hash = "";
      const response = await fetch(requestUrl, {
        headers: { "X-Requested-With": "directory-filter" },
      });
      if (!response.ok) throw new Error("Directory request failed");

      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const replacement = page.querySelector("#browse");
      if (!replacement) throw new Error("Directory response was incomplete");

      current.replaceWith(replacement);
      if (updateHistory) history.pushState({}, "", url);
      window.scrollTo(0, scrollPosition);
      replacement.querySelector(".tabs a[aria-current='page']")?.focus({ preventScroll: true });
    } catch (_error) {
      window.location.assign(url);
    }
  };

  document.addEventListener("click", (event) => {
    const link = event.target.closest("#browse .tabs a");
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    replaceDirectory(link.href, true);
  });

  window.addEventListener("popstate", () => replaceDirectory(window.location.href, false));
})();
