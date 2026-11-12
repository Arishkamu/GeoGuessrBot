import { fmt } from '../utils.js'

export default function UserScore({ profile, demo }) {
  if (demo) {
    return (
      <div className="user-score">
        Демо-очки не входят в общий счёт
      </div>
    )
  }

  return (
    <div className="user-score" role="status">
      <span>Очки за всё время</span>

      <strong className="num">
        {profile.error
          ? 'Не удалось загрузить'
          : profile.total === null
            ? 'Загрузка…'
            : fmt(profile.total)}
      </strong>
    </div>
  )
}
