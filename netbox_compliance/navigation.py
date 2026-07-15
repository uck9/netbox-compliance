from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

#
# Definitions
#

measure_buttons = [
    PluginMenuButton(
        link='plugins:netbox_compliance:compliancemeasure_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_compliance.add_compliancemeasure'],
    ),
]

package_buttons = [
    PluginMenuButton(
        link='plugins:netbox_compliance:compliancepackage_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_compliance.add_compliancepackage'],
    ),
]

definitions_items = (
    PluginMenuItem(
        link='plugins:netbox_compliance:compliancemeasure_list',
        link_text='Measures',
        permissions=['netbox_compliance.view_compliancemeasure'],
        buttons=measure_buttons,
    ),
    PluginMenuItem(
        link='plugins:netbox_compliance:compliancepackage_list',
        link_text='Packages',
        permissions=['netbox_compliance.view_compliancepackage'],
        buttons=package_buttons,
    ),
)

#
# Assignments
#

package_assignment_buttons = [
    PluginMenuButton(
        link='plugins:netbox_compliance:packageassignment_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_compliance.add_packageassignment'],
    ),
]

measure_assignment_buttons = [
    PluginMenuButton(
        link='plugins:netbox_compliance:measureassignment_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_compliance.add_measureassignment'],
    ),
]

assignments_items = (
    PluginMenuItem(
        link='plugins:netbox_compliance:packageassignment_list',
        link_text='Package Assignments',
        permissions=['netbox_compliance.view_packageassignment'],
        buttons=package_assignment_buttons,
    ),
    PluginMenuItem(
        link='plugins:netbox_compliance:measureassignment_list',
        link_text='Measure Assignments',
        permissions=['netbox_compliance.view_measureassignment'],
        buttons=measure_assignment_buttons,
    ),
)

#
# Exemptions
#

exemption_buttons = [
    PluginMenuButton(
        link='plugins:netbox_compliance:complianceexemption_add',
        title='Add',
        icon_class='mdi mdi-plus-thick',
        permissions=['netbox_compliance.add_complianceexemption'],
    ),
]

exemptions_items = (
    PluginMenuItem(
        link='plugins:netbox_compliance:complianceexemption_list',
        link_text='Exemptions',
        permissions=['netbox_compliance.view_complianceexemption'],
        buttons=exemption_buttons,
    ),
)

#
# Results & Reports
#

results_items = (
    PluginMenuItem(
        link='plugins:netbox_compliance:complianceresult_list',
        link_text='Results',
        permissions=['netbox_compliance.view_complianceresult'],
    ),
    PluginMenuItem(
        link='plugins:netbox_compliance:compliancesnapshot_list',
        link_text='Snapshots',
        permissions=['netbox_compliance.view_compliancesnapshot'],
    ),
    PluginMenuItem(
        link='plugins:netbox_compliance:monthly_report',
        link_text='Monthly Report',
        permissions=['netbox_compliance.view_compliancesnapshot'],
    ),
)

menu = PluginMenu(
    label='Compliance',
    icon_class='mdi mdi-shield-check-outline',
    groups=(
        ('Definitions', definitions_items),
        ('Assignments', assignments_items),
        ('Exemptions', exemptions_items),
        ('Results & Reports', results_items),
    ),
)
