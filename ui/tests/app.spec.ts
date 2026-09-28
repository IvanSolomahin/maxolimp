import { expect, test } from "@playwright/test";

const taskId = "00000000-0000-0000-0000-000000000001";
const task = {
  id: taskId,
  title: "Проверочная задача",
  statement: "Сколько будет $2+2$?",
  answer: "4",
  difficulty: 2,
  subject: "math",
  grade: 8,
  topics: [{ id: "t1", name: "Арифметика" }],
  olympiads: [{ id: "o1", name: "Тестовая олимпиада", short_name: "Тест" }],
  source: { url: null, year: null, stage: null, number: "1" },
  has_solution: true,
  hints_count: 0,
};

test.beforeEach(async ({ page }, testInfo) => {
  if (!testInfo.title.includes('MAX initData')) {
    await page.route('https://st.max.ru/js/max-web-app.js', (route) =>
      route.fulfill({ contentType: 'application/javascript', body: '' }),
    );
  }
  await page.route("**/api/tasks/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/solutions"))
      return route.fulfill({
        json: {
          items: [
            {
              id: "s1",
              content: "Сложить два и два.",
              is_generated: false,
              is_verified: true,
            },
          ],
        },
      });
    if (url.pathname.endsWith(`/${taskId}`))
      return route.fulfill({ json: task });
    if (url.pathname.endsWith("/tasks"))
      return route.fulfill({
        json: {
          total: 1,
          page: 1,
          size: 20,
          items: [
            {
              id: taskId,
              title: task.title,
              snippet: task.statement,
              difficulty: 2,
              olympiad: "Тестовая олимпиада",
              olympiad_short_name: "Тест",
              number: "1",
            },
          ],
        },
      });
    if (url.pathname.endsWith("/olympiads"))
      return route.fulfill({
        json: {
          items: [{ id: "o1", name: "Тестовая олимпиада", short_name: "Тест" }],
        },
      });
    return route.fulfill({ status: 404, json: {} });
  });
});

test("search, answer and statistics use real task data", async ({ page }) => {
  await page.goto("/tasks");
  await expect(
    page.getByRole("heading", { name: "Проверочная задача" }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Проверочная задача/ }).click();
  await expect(page).toHaveURL(new RegExp(`/tasks/${taskId}$`));
  await expect(page.getByText("Эталонный ответ")).toHaveCount(0);
  await page.getByLabel("Ответ").fill("4");
  await page.getByRole("button", { name: "Отправить ответ" }).click();
  await expect(page.getByText("Эталонный ответ")).toBeVisible();
  await expect(page.getByText("Сложить два и два.")).toBeVisible();
  await page.getByRole("button", { name: "Отметить решённой" }).click();
  await page.goto("/statistics");
  await expect(page.getByText("Проверочная задача")).toBeVisible();
  await expect(
    page.locator(".count-row").getByText("Тестовая олимпиада"),
  ).toBeVisible();
});

test("practice has tasks from API and no invented queue", async ({ page }) => {
  await page.goto("/practice");
  await expect(
    page.getByRole("heading", { name: "Проверочная задача" }),
  ).toBeVisible();
  await expect(page.getByText("Задача 1 из 1")).toBeVisible();
});

test("legacy route and mobile navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/olympiad-task-solve.html?topic=3");
  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("navigation", { name: "Разделы" })).toBeVisible();
  await page
    .getByRole("navigation", { name: "Разделы" })
    .getByRole("link", { name: "Статистика" })
    .click();
  await expect(page).toHaveURL(/\/statistics$/);
});

test("MAX initData is validated when present", async ({ page }) => {
  await page.route("https://st.max.ru/js/max-web-app.js", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: 'window.WebApp = { initData: "test-init-data" };',
    }),
  );
  let validated = false;
  await page.route("**/api/max/validate", async (route) => {
    validated = route.request().postDataJSON().initData === "test-init-data";
    await route.fulfill({ json: { valid: true, max_id: 10, user: {} } });
  });
  await page.goto("/");
  await expect.poll(() => validated).toBe(true);
});

test("olympiad selection opens details from API", async ({ page }) => {
  await page.route("**/api/olympiads/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/universities"))
      return route.fulfill({
        json: {
          total: 1,
          page: 1,
          size: 100,
          items: [{ id: 7, name: "Университет", cities: ["Москва"] }],
        },
      });
    if (path.endsWith("/universities/7/programs"))
      return route.fulfill({
        json: {
          total: 1,
          page: 1,
          size: 100,
          items: [{ id: 3, name: "Информатика", code: "01.03.02" }],
        },
      });
    if (path.endsWith("/recommendations"))
      return route.fulfill({
        json: {
          total: 1,
          page: 1,
          size: 20,
          items: [
            {
              id: 11,
              name: "Олимпиада А",
              subject: { id: 1, name: "Математика" },
              complexity: 3,
              benefit: { type: "bvi" },
            },
          ],
        },
      });
    if (path.endsWith("/olympiads/11/stages"))
      return route.fulfill({ json: { items: [] } });
    if (path.endsWith("/olympiads/11"))
      return route.fulfill({
        json: {
          id: 11,
          name: "Олимпиада А",
          complexity: 3,
          description: "Описание олимпиады",
          host_university: { id: 7, name: "Университет" },
          subjects: [{ id: 1, name: "Математика" }],
        },
      });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto("/olympiads");
  await page.getByRole("button", { name: /Университет/ }).click();
  await page.getByRole("button", { name: /Информатика/ }).click();
  await expect(
    page.getByRole("heading", { name: "Олимпиада А" }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Подробнее/ }).click();
  await expect(page).toHaveURL(/\/olympiads\/11$/);
  await expect(page.getByText("Описание олимпиады")).toBeVisible();
});

test("legacy solved titles stay in archive without dated metrics", async ({
  page,
}) => {
  await page.addInitScript(() =>
    localStorage.setItem("maxolimp-solved", JSON.stringify(["Старая задача"])),
  );
  await page.goto("/statistics");
  await expect(page.getByText("Старая задача")).toBeVisible();
  await expect(page.getByText("дата неизвестна")).toBeVisible();
  await expect(
    page.getByText("За выбранный период нет отметок о решении."),
  ).toBeVisible();
});

test("direct task URL reloads and an API failure offers retry", async ({
  page,
}) => {
  await page.goto(`/tasks/${taskId}`);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Проверочная задача" }),
  ).toBeVisible();
  await page.route("**/api/tasks/tasks?**", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.goto("/tasks");
  await expect(
    page.getByRole("heading", { name: "Не удалось загрузить данные" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Повторить" })).toBeVisible();
});
