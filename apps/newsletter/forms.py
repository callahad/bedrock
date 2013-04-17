# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from django import forms
from django.core.exceptions import ValidationError
from django.forms import widgets
from django.utils.safestring import mark_safe

from mozorg.forms import (
    FORMATS, LANGS, EmailInput, PrivacyWidget,
    SideRadios, get_lang_choices
)
from product_details import product_details
from tower import ugettext as _

# Cannot use short "from . import utils" because we need to mock
# utils.get_newsletters in our tests
from newsletter import utils


def newsletter_title(newsletter):
    """Given a newsletter's key, return its title if we can,
    otherwise return the key
    """
    newsletters = utils.get_newsletters()
    if newsletter in newsletters and 'title' in newsletters[newsletter]:
        return newsletters[newsletter]['title']
    return newsletter


class UnlabeledTableCellRadios(widgets.RadioFieldRenderer):
    """Render radio buttons as table cells, without their labels"""

    def render(self):
        radios = [w.tag() for w in self]
        if radios:
            return mark_safe('<td>' + '</td><td>'.join(radios) + "</td>")
        return mark_safe('')


class BooleanRadioRenderer(widgets.RadioFieldRenderer):
    """Return a boolean with two radio buttons, the first meaning
    true and the second false, rendered as two table cells.
    """
    def render(self):
        if self.value == 'True':
            trueattrs = 'checked=checked'
            falseattrs = ''
        else:
            trueattrs = ''
            falseattrs = 'checked=checked'
        template = \
            """
            <td>
              <input type="radio" name="{name}" {trueattrs} value="True">
            </td>
            <td>
              <input type="radio" name="{name}" {falseattrs} value="False">
            </td>
            """
        result = template.format(
            name=self.name,
            trueattrs=trueattrs,
            falseattrs=falseattrs
        )
        return mark_safe(result)


class TableCheckboxInput(widgets.CheckboxInput):
    """Add table cell markup around the rendered checkbox, so we can use
    it interchangeably with the BooleanRadioRenderer"""
    def render(self, *args, **kwargs):
        out = super(TableCheckboxInput, self).render(*args, **kwargs)
        return mark_safe("<td>" + out + "</td>")


class ManageSubscriptionsForm(forms.Form):
    """
    Form used on manage subscriptions page for the user's information,
    like email address and language preference.

    @param locale: locale string, e.g. "en-US".  Will be used to set
    country and lang defaults if not otherwise provided in initial
    or bound data.
    @param args: Other standard form args
    @param kwargs: Other standard form kwargs
    """

    email = forms.EmailField(widget=EmailInput(attrs={'required': 'true'}))
    format = forms.ChoiceField(widget=forms.RadioSelect(renderer=SideRadios),
                               choices=FORMATS,
                               initial='H')
    remove_all = forms.BooleanField(required=False)
    LANG_CHOICES = get_lang_choices()

    country = forms.ChoiceField(choices=[],  # will set choices based on locale
                                required=False)
    lang = forms.ChoiceField(choices=LANG_CHOICES,
                             required=False)

    def __init__(self, locale, *args, **kwargs):
        regions = product_details.get_regions(locale)
        regions = sorted(regions.iteritems(), key=lambda x: x[1])

        lang = country = locale.lower()
        if '-' in lang:
            lang, country = lang.split('-', 1)
        lang = lang if lang in LANGS else 'en'

        self.newsletters = kwargs.pop('newsletters', [])

        initial = kwargs.get('initial', {})
        if not initial.get('country', None):
            initial['country'] = country
        if not initial.get('lang', None):
            initial['lang'] = lang
        kwargs['initial'] = initial

        super(ManageSubscriptionsForm, self).__init__(*args, **kwargs)
        self.fields['country'].choices = regions
        self.already_subscribed = initial.get('newsletters', [])

    def clean(self):
        valid_newsletters = utils.get_newsletters()
        for newsletter in self.newsletters:
            if newsletter not in valid_newsletters:
                msg = _("%s is not a valid newsletter") % newsletter
                raise ValidationError(msg)
        return super(ManageSubscriptionsForm, self).clean()


class NewsletterForm(forms.Form):
    """Form to let a user subscribe to or unsubscribe from a newsletter"""
    title = forms.CharField(required=False)
    description = forms.CharField(required=False)
    subscribed = forms.BooleanField(
        widget=forms.RadioSelect(renderer=BooleanRadioRenderer),
        required=False,  # they have to answer, but answer can be False
    )
    newsletter = forms.CharField(widget=forms.HiddenInput)
    # another hidden one, just so the template can get the data
    english_only = forms.BooleanField(required=False)


class NewsletterFooterForm(forms.Form):
    newsletter = forms.CharField(widget=forms.HiddenInput)
    email = forms.EmailField(widget=EmailInput(attrs={'required': 'true'}))
    fmt = forms.ChoiceField(widget=forms.RadioSelect(renderer=SideRadios),
                            choices=FORMATS,
                            initial='H')
    privacy = forms.BooleanField(widget=PrivacyWidget)
    source_url = forms.URLField(verify_exists=False, required=False)

    LANG_CHOICES = get_lang_choices()

    def __init__(self, locale, *args, **kwargs):
        regions = product_details.get_regions(locale)
        regions = sorted(regions.iteritems(), key=lambda x: x[1])

        lang = country = locale.lower()
        if '-' in lang:
            lang, country = lang.split('-', 1)
        lang = lang if lang in LANGS else 'en'

        super(NewsletterFooterForm, self).__init__(*args, **kwargs)
        self.fields['country'] = forms.ChoiceField(choices=regions,
                                                   initial=country,
                                                   required=False)
        self.fields['lang'] = forms.ChoiceField(choices=self.LANG_CHOICES,
                                                initial=lang,
                                                required=False)

    def clean_newsletter(self):
        # We didn't want to have to look up the list of valid newsletters
        # until we actually had a form submitted
        if 'newsletter' in self.cleaned_data:
            valid_newsletters = utils.get_newsletters().keys()
            if self.cleaned_data['newsletter'] not in valid_newsletters:
                raise ValidationError("%s is not a valid newsletter" %
                                      self.cleaned_data['newsletter'])
            return self.cleaned_data['newsletter']