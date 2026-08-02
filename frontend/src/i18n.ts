import i18n from 'i18next'
import{initReactI18next}from'react-i18next'

const common={
 title:'iRacing Analyst',sessions:'Sessions',import:'Import telemetry',waiting:'Waiting for iRacing or LMU',recording:'Recording',
 best:'Best lap',median:'Median pace',optimal:'Sector optimal',potential:'Potential gap',corners:'Corners and zones',
 noSession:'Import an IBT/DuckDB/NPZ file or complete an iRacing or LMU session.',selected:'Best',reference:'Median',sourceLap:'Source lap',
 loss:'Available gain',speed:'Speed',throttle:'Throttle',brake:'Brake',steering:'Steering',delta:'Delta',map:'Track and racing line',
 whyFaster:'Why this lap was faster',improve:'What to improve next run',noInsights:'No reliable difference was found yet.',
 delete:'Delete',clear:'Clear test data',confirmClear:'Delete every locally recorded session?',validLaps:'valid laps',turns:'turns',
 trajectoryMissing:'The racing line was not recorded in this older session.',confirmed:'Confirmed',probable:'Probable',insufficient:'Not enough data',zone:'Zone',
 'data.ready':'Enough laps for reliable comparisons.','data.limited':'Initial comparison; repeat the session to confirm the pattern.',
 'data.needMoreLaps':'Complete at least 3 valid laps to compare best and median.','data.noValidLaps':'No complete valid laps were recorded.','data.insufficient':'This legacy report does not contain enough structured data.',
 'quality.recovered':'Reconnect or reset fragments were recovered and invalid portions were excluded.','quality.corrupted':'Some telemetry is damaged. Potential and recommendations are hidden when they cannot be verified.',
 'insight.faster.title':'Best lap gained time here','insight.faster.message':'This section was measurably faster than your median lap.',
 'rec.inconsistent.title':'Build consistency','rec.inconsistent.message':'Repeat the reference inputs before pushing the entry. This segment has the largest spread.',
 'rec.lateThrottle.title':'Reach full throttle earlier','rec.lateThrottle.message':'The throttle ramp is long after the apex. Prioritize rotation before acceleration.',
 'rec.lowSpeed.title':'Protect minimum speed','rec.lowSpeed.message':'Avoid over-slowing the car; use the source lap as the entry reference.',
 'rec.corrections.title':'Reduce steering corrections','rec.corrections.message':'Unwind the steering progressively and delay throttle if the car is not settled.',
 'rec.segment.title':'Focus on this segment','rec.segment.message':'Reproduce the source lap inputs; this is the largest confirmed time opportunity.',
 wholeLap:'Whole lap',differences:'Main differences',trackOrder:'Track order',bestVsMedian:'Best vs Median',remainingPotential:'Remaining potential',gain:'gain',lossLabel:'loss',laps:'Laps',lap:'Lap',lapTime:'Lap time',statusLabel:'Status',distance:'Distance',openEvidence:'open evidence',sameTechnique:'No measurable technique difference',
 'reason.time':'segment time','reason.brake_start':'braking point','reason.brake_release':'brake release','reason.throttle_start':'initial throttle','reason.full_throttle':'full throttle','reason.minimum_speed':'minimum speed','reason.exit_speed':'exit speed',
 'insight.time.title':'Faster segment time','insight.time.message':'The selected lap completed this corner faster.','insight.brake_start.title':'Different braking point','insight.brake_start.message':'The measurable braking-point change accompanied a time gain.','insight.brake_release.title':'Cleaner brake release','insight.brake_release.message':'Brake release changed together with a faster corner.','insight.throttle_start.title':'Earlier acceleration phase','insight.throttle_start.message':'Initial throttle timing helped the exit.','insight.full_throttle.title':'Full throttle changed','insight.full_throttle.message':'Full throttle timing accompanied a measurable gain.','insight.minimum_speed.title':'More minimum speed','insight.minimum_speed.message':'The faster lap carried a measurable speed difference at apex.','insight.exit_speed.title':'Stronger exit','insight.exit_speed.message':'Higher exit speed contributed to the gain.',
 'fact.brake_start':'Brake start','fact.brake_release':'Brake release','fact.throttle_start':'Throttle start','fact.full_throttle':'Full throttle','fact.minimum_speed':'Minimum speed','fact.exit_speed':'Exit speed','fact.steering_corrections':'Steering corrections',
 'badge.best':'Best','badge.median':'Median','badge.clean':'Clean','badge.out_lap':'Out lap','badge.in_lap':'In lap','badge.pit':'Pit','badge.incomplete':'Incomplete','badge.invalid':'Invalid','badge.incident_1x':'Incident 1x','badge.incident_2x':'Incident 2x','badge.incident_4x':'Incident 4x',outShort:'Out',deleteSession:'Delete session'
}
const ru={
 ...common,title:'iRacing Аналитик',sessions:'Сессии',import:'Импорт телеметрии',waiting:'Ожидание iRacing или LMU',recording:'Идёт запись',
 best:'Лучший круг',median:'Медианный темп',optimal:'Sector Optimal',potential:'Потенциал',corners:'Повороты и зоны',
 noSession:'Импортируйте IBT/DuckDB/NPZ или завершите сессию iRacing либо LMU.',selected:'Лучший',reference:'Медианный',sourceLap:'Круг-источник',
 loss:'Доступный выигрыш',speed:'Скорость',throttle:'Газ',brake:'Тормоз',steering:'Руль',delta:'Дельта',map:'Карта и траектория',
 whyFaster:'Почему этот круг быстрее',improve:'Что улучшить в следующем заезде',noInsights:'Надёжной разницы пока не найдено.',
 delete:'Удалить',clear:'Удалить тестовые данные',confirmClear:'Удалить все локально записанные сессии?',validLaps:'валидных кругов',turns:'поворотов',
 trajectoryMissing:'В этой старой сессии траектория не записывалась.',confirmed:'Подтверждено',probable:'Вероятно',insufficient:'Мало данных',zone:'Зона',
 'data.ready':'Кругов достаточно для надёжного сравнения.','data.limited':'Первичный вывод: повторите сессию, чтобы подтвердить закономерность.',
 'data.needMoreLaps':'Проедьте минимум 3 валидных круга для сравнения лучшего и медианного.','data.noValidLaps':'Не записано ни одного полного валидного круга.','data.insufficient':'В старом отчёте недостаточно структурированных данных.',
 'quality.recovered':'Фрагменты после reconnect или reset восстановлены, повреждённые участки исключены.','quality.corrupted':'Часть телеметрии повреждена. Потенциал и рекомендации скрыты, если их нельзя проверить.',
 'insight.faster.title':'Здесь лучший круг выиграл время','insight.faster.message':'Этот участок пройден измеримо быстрее медианного круга.',
 'rec.inconsistent.title':'Закрепи повторяемость','rec.inconsistent.message':'Сначала повтори действия референса, не переатаковывая вход: здесь самый большой разброс.',
 'rec.lateThrottle.title':'Раньше выходи на полный газ','rec.lateThrottle.message':'После апекса газ набирается долго. Сосредоточься на повороте машины до разгона.',
 'rec.lowSpeed.title':'Сохрани минимальную скорость','rec.lowSpeed.message':'Не замедляй машину лишний раз; используй круг-источник как ориентир входа.',
 'rec.corrections.title':'Уменьши коррекции рулём','rec.corrections.message':'Плавно распускай руль и не добавляй газ, пока машина не стабилизирована.',
 'rec.segment.title':'Сосредоточься на сегменте','rec.segment.message':'Повтори действия круга-источника: здесь подтверждена крупнейшая потеря времени.',
 wholeLap:'Весь круг',differences:'Главные отличия',trackOrder:'По трассе',bestVsMedian:'Best vs Median',remainingPotential:'Остаточный потенциал',gain:'выигрыш',lossLabel:'потеря',laps:'Круги',lap:'Круг',lapTime:'Время круга',statusLabel:'Статус',distance:'Дистанция',openEvidence:'открыть доказательства',sameTechnique:'Измеримой разницы в технике нет',
 'reason.time':'время сегмента','reason.brake_start':'точка торможения','reason.brake_release':'отпускание тормоза','reason.throttle_start':'начало газа','reason.full_throttle':'полный газ','reason.minimum_speed':'минимальная скорость','reason.exit_speed':'скорость выхода',
 'insight.time.title':'Быстрее пройден сегмент','insight.time.message':'Выбранный круг прошёл этот поворот быстрее.','insight.brake_start.title':'Изменилась точка торможения','insight.brake_start.message':'Измеримое изменение торможения сопровождалось выигрышем времени.','insight.brake_release.title':'Чище отпущен тормоз','insight.brake_release.message':'Изменение отпускания тормоза совпало с более быстрым поворотом.','insight.throttle_start.title':'Раньше начат разгон','insight.throttle_start.message':'Момент начала газа помог выходу.','insight.full_throttle.title':'Изменился полный газ','insight.full_throttle.message':'Момент полного газа сопровождался измеримым выигрышем.','insight.minimum_speed.title':'Выше минимальная скорость','insight.minimum_speed.message':'В быстром круге есть измеримая разница скорости в апексе.','insight.exit_speed.title':'Сильнее выход','insight.exit_speed.message':'Более высокая скорость выхода дала выигрыш.',
 'fact.brake_start':'Начало тормоза','fact.brake_release':'Отпускание тормоза','fact.throttle_start':'Начало газа','fact.full_throttle':'Полный газ','fact.minimum_speed':'Минимальная скорость','fact.exit_speed':'Скорость выхода','fact.steering_corrections':'Коррекции рулём',
 'badge.best':'Лучший','badge.median':'Медианный','badge.clean':'Чистый','badge.out_lap':'Out lap','badge.in_lap':'In lap','badge.pit':'Пит','badge.incomplete':'Незавершённый','badge.invalid':'Невалидный','badge.incident_1x':'Инцидент 1x','badge.incident_2x':'Инцидент 2x','badge.incident_4x':'Инцидент 4x',outShort:'Out',deleteSession:'Удалить сессию'
}
i18n.use(initReactI18next).init({resources:{en:{translation:common},ru:{translation:ru}},lng:localStorage.getItem('language')||'ru',fallbackLng:'en',interpolation:{escapeValue:false}})
export default i18n
