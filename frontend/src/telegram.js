// Обёртка над Telegram WebApp. Вне Telegram (в обычном браузере) все функции безопасно ничего не делают.
export const tg = window.Telegram?.WebApp ?? null

export function initTelegram() {
  if (!tg) return
  tg.ready()
  tg.expand()
  // иначе свайп вниз по панораме сворачивает мини-апп
  try { tg.disableVerticalSwipes?.() } catch (e) { /* старые версии Telegram */ }
  // шапка, фон и нижняя панель Telegram красятся в цвет приложения
  for (const fn of ['setHeaderColor', 'setBackgroundColor', 'setBottomBarColor']) {
    try { tg[fn]('bg_color') } catch (e) { /* старые версии Telegram */ }
  }
}

export const initData = () => tg?.initData ?? ''

export function isDark() {
  if (tg?.colorScheme) return tg.colorScheme === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

// подписка на смену темы; возвращает функцию отписки
export function onThemeChange(cb) {
  if (tg) {
    tg.onEvent('themeChanged', cb)
    return () => tg.offEvent('themeChanged', cb)
  }
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', cb)
  return () => mq.removeEventListener('change', cb)
}

export function haptic(kind = 'light') {
  try { tg?.HapticFeedback.impactOccurred(kind) } catch (e) { /* не критично */ }
}

export function share(text) {
  const url = encodeURIComponent(window.location.origin)
  if (tg?.openTelegramLink) tg.openTelegramLink(`https://t.me/share/url?url=${url}&text=${encodeURIComponent(text)}`)
  else if (navigator.share) navigator.share({ text })
}
