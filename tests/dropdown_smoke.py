"""Exercise custom selects against the running setup page, without provider calls."""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--screenshots-dir', type=Path)
    args = parser.parse_args()
    errors, submissions = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/sessions', lambda route: (submissions.append(route.request.method), route.abort()))
        page.goto(args.base_url + '/dev-login')
        expect(page.locator('#session-form select')).to_have_count(0, timeout=3000)
        expect(page.get_by_role('combobox')).to_have_count(1)

        def trigger(name):
            return page.locator(f'[data-select="{name}"] [role=combobox]')

        def menu(name):
            return page.locator(f'#setup-select-{name}-menu')

        def choose(name, label):
            trigger(name).click()
            page.get_by_role('option', name=label, exact=True).click()

        defaults = page.evaluate('Object.fromEntries(["language","gender","level"].map(name => [name, document.querySelector(`input[name="${name}"]`).value]))')
        page.evaluate('''() => {
          window.__languageEvents=[];
          for (const type of ['input','change']) document.querySelector('[name=language]').addEventListener(type, event => window.__languageEvents.push(event.type));
        }''')
        choose('language', 'English')
        expect(page.locator('[name=language]')).to_have_value('en')
        expect(trigger('language')).to_have_attribute('aria-expanded', 'false')
        assert page.evaluate('window.__languageEvents') == ['input', 'change']

        trigger('language').focus()
        page.keyboard.press('Space')
        expect(menu('language')).to_be_visible()
        page.keyboard.press('Home')
        expect(trigger('language')).to_have_attribute('aria-activedescendant', 'setup-select-language-option-0')
        page.keyboard.press('Escape')
        expect(page.locator('[name=language]')).to_have_value('en')
        expect(trigger('language')).to_be_focused()
        page.keyboard.press('b')
        page.keyboard.press('Enter')
        expect(page.locator('[name=language]')).to_have_value('id')
        page.keyboard.press('ArrowDown')
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
        expect(page.locator('[name=language]')).to_have_value('en')
        assert page.evaluate('document.activeElement.name === "question_count"')

        trigger('language').click()
        page.get_by_role('heading', name='Siapkan Ruang Wawancara').click()
        expect(trigger('language')).to_have_attribute('aria-expanded', 'false')
        page.locator('#setup-context > summary').click()
        choose('gender', 'Perempuan')
        expect(page.locator('[name=gender]')).to_have_value('female')
        trigger('gender').click()
        trigger('level').click()
        expect(page.get_by_role('listbox')).to_have_count(1)
        expect(trigger('gender')).to_have_attribute('aria-expanded', 'false')
        page.keyboard.press('End')
        page.keyboard.press('Enter')
        expect(page.locator('[name=level]')).to_have_value('manager')
        page.keyboard.press('m')
        expect(trigger('level')).to_have_attribute('aria-activedescendant', 'setup-select-level-option-1')
        page.keyboard.press('m')
        expect(trigger('level')).to_have_attribute('aria-activedescendant', 'setup-select-level-option-3')
        page.keyboard.press('Escape')
        choose('level', 'Senior')
        assert page.evaluate('''() => {
          const data=new FormData(document.querySelector('#session-form'));
          return data.get('language')==='en' && data.get('gender')==='female' && data.get('level')==='senior';
        }''')

        page.set_viewport_size({'width':1440,'height':768})
        trigger('level').scroll_into_view_if_needed()
        page.locator('.setup-options-scroll').evaluate('''panel => {
          const button=panel.querySelector('[data-select="level"] [role=combobox]');
          panel.scrollTop += button.getBoundingClientRect().bottom - (panel.getBoundingClientRect().bottom-12);
        }''')
        trigger('level').click()
        bounds=menu('level').evaluate('''list => {
          const menu=list.getBoundingClientRect();
          const trigger=document.querySelector('[data-select="level"] [role=combobox]').getBoundingClientRect();
          return {top:menu.top,bottom:menu.bottom,left:menu.left,right:menu.right,above:menu.bottom<=trigger.top,portal:list.parentElement===document.body};
        }''')
        assert bounds['above'] and bounds['portal'], bounds
        assert bounds['top']>=8 and bounds['bottom']<=768-8, bounds
        page.locator('.setup-options-scroll').evaluate('panel => {panel.scrollTop=0;}')
        expect(trigger('level')).to_have_attribute('aria-expanded', 'false')
        page.locator('#setup-context > summary').click()

        for width in (320,390,768,1440):
            page.set_viewport_size({'width':width,'height':844})
            trigger('language').click()
            bounds=menu('language').evaluate('list => {const r=list.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom};}')
            assert bounds['left']>=8 and bounds['right']<=width-8, bounds
            assert bounds['top']>=8 and bounds['bottom']<=844-8, bounds
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.keyboard.press('Escape')

        trigger('language').click()
        page.evaluate('document.querySelector("#session-form").reset()')
        expect(trigger('language')).to_have_attribute('aria-expanded', 'false')
        for name,value in defaults.items():
            expect(page.locator(f'[name={name}]')).to_have_value(value)

        touch = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
        mobile = touch.new_page()
        mobile.on('pageerror', lambda error: errors.append(str(error)))
        mobile.route('**/api/sessions', lambda route: (submissions.append(route.request.method), route.abort()))
        mobile.goto(args.base_url + '/dev-login')
        mobile.locator('[data-select="language"] [role=combobox]').tap()
        mobile.get_by_role('option', name='English', exact=True).tap()
        expect(mobile.locator('[name=language]')).to_have_value('en')
        mobile.locator('#setup-context > summary').tap()
        mobile.locator('[data-select="gender"] [role=combobox]').tap()
        mobile.get_by_role('option', name='Perempuan', exact=True).tap()
        expect(mobile.locator('[name=gender]')).to_have_value('female')
        mobile.locator('[data-select="level"] [role=combobox]').tap()
        mobile.get_by_role('option', name='Manager', exact=True).tap()
        expect(mobile.locator('[name=level]')).to_have_value('manager')
        touch.close()
        page.bring_to_front()
        assert not submissions, 'Dropdown interaction must never submit the form'
        assert not errors, errors

        if args.screenshots_dir:
            args.screenshots_dir.mkdir(parents=True,exist_ok=True)
            page.reload()
            page.evaluate('document.fonts.ready')
            page.set_viewport_size({'width':1440,'height':900})
            trigger('language').click()
            page.screenshot(path=str(args.screenshots_dir/'dropdown-desktop.png'))
            page.keyboard.press('Escape')
            page.set_viewport_size({'width':390,'height':844})
            trigger('language').click()
            page.screenshot(path=str(args.screenshots_dir/'dropdown-mobile.png'))
        browser.close()
    print('PASS: custom selects, pointer/touch/keyboard/typeahead, Escape/Tab, outside dismissal, single popup, payload/reset, portal bounds and narrow layouts. No session/provider calls.')


if __name__ == '__main__':
    main()
