import { useTranslation } from 'react-i18next'

import type { Member } from '../api/client'
import { Select } from './ui'

/**
 * Whom a Message is for: everyone in the Topic, a Member (any of their Assistants
 * may answer) or one specific Assistant. The value is the name the server resolves.
 */
export function AddresseeSelect({
  members,
  value,
  onChange,
  id,
}: {
  members: Member[]
  value: string
  onChange: (value: string) => void
  id?: string
}) {
  const { t } = useTranslation()
  const named = members.filter((member) => member.pseudonym)
  return (
    <Select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{t('compose.toEveryone')}</option>
      {named.map((member) => (
        <optgroup key={member.user_id} label={member.pseudonym ?? ''}>
          <option value={member.pseudonym ?? ''}>{t('compose.toMember', { name: member.pseudonym })}</option>
          {member.assistants.map((assistant) => (
            <option key={assistant.id} value={assistant.name}>
              {assistant.name}
            </option>
          ))}
        </optgroup>
      ))}
    </Select>
  )
}
