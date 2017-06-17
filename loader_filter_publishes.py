# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import re
import sgtk
from sgtk import Hook


class FilterPublishes(Hook):
    """
    Hook that can be used to filter the list of publishes returned from Shotgun for the current
    location
    """

    def execute(self, publishes, **kwargs):
        """
        Main hook entry point
        
        :param publishes:    List of dictionaries 
                             A list of  dictionaries for the current location within the app.  Each
                             item in the list is a Dictionary of the form:
                             
                             {
                                 "sg_publish" : {Shotgun entity dictionary for a Published File entity}
                             }
                             
                                                         
        :return List:        The filtered list of dictionaries of the same form as the input 'publishes' 
                             list
        """
        app = self.parent
        # the default implementation just returns the unfiltered list:
        current_engine = sgtk.platform.current_engine()
        if not current_engine.name == "tk-maya":
            return publishes
        context = current_engine.context
        task = context.task
        if not task:
            return publishes
        project = context.project
        entity = context.entity
        entity_type = entity["type"]
        step = context.step
        step_name = step["name"]
        tk = sgtk.tank_from_entity("Task", task["id"])
        sg = tk.shotgun
        if entity_type == "Asset" and step_name == "Model":
            return self.filter_asset_mdl(publishes, task)
        elif entity_type == "Asset" and step_name in ["Rig", "Surface"]:
            return self.filter_asset_rig(publishes, sg)
        elif entity_type == "Asset" and step_name == "Texture":
            return self.filter_asset_texture(publishes, sg, task)
        elif entity_type == "Shot" and step_name == "Layout":
            return self.filter_shot_lay(publishes, sg, task)
        elif entity_type == "Shot" and step_name == "Animation":
            return self.filter_shot_anim(publishes, sg)
        elif entity_type == "Shot" and step_name in ["CFX", "VFX"]:
            return self.filter_shot_cfx(publishes, sg)
        elif entity_type == "Shot" and step_name == "Lighting":
            return self.filter_shot_lgt(publishes, sg)
        else:
            return publishes

    @staticmethod
    def get_task_step(sg, task):
        task_info = sg.find_one("Task", [["id", "is", task["id"]]], ["step.Step.short_name"])
        return task_info["step.Step.short_name"]

    @staticmethod
    def get_assets_of_entity(sg, entity):
        entity = sg.find_one(entity["type"], [["id", "is", entity["id"]]], ["assets"])
        return entity["assets"]

    @staticmethod
    def suffix_match(base_name, suffix_list):
        for suffix_str in suffix_list:
            if re.findall("%s$" % suffix_str, base_name):
                return True
                break
        return False

    def filter_publishes(self, publishes, sg=None, filter_type="Asset",
                         task_list=list(), path_suffix_list=list(), published_file_type_name_list=list(),
                         task_name_suffix_list=list(), step_list=list()):
        publish_list = list()
        filter_entity = filter_task = filter_file_type = filter_path = filter_step = True
        if publishes:
            current_entity_type = publishes[0]["sg_publish"]["entity"]["type"]
            if current_entity_type == filter_type:
                for publish in publishes:
                    sg_publish = publish["sg_publish"]
                    task_name = sg_publish["task"]["name"]
                    if task_list:
                        filter_task = sg_publish["task"] in task_list
                    if path_suffix_list:
                        windows_path = sg_publish["path"]["local_path_windows"]
                        base_name = os.path.basename(windows_path)
                        filter_path = self.suffix_match(base_name, path_suffix_list)
                    if published_file_type_name_list:
                        filter_file_type = sg_publish["published_file_type"]["name"] in published_file_type_name_list
                    if task_name_suffix_list:
                        if "_" in task_name:
                            filter_task_name = task_name.split("_")[-1] in task_name_suffix_list
                        else:
                            filter_task_name = False
                    else:
                        filter_task_name = "_" not in task_name
                    if sg and step_list:
                        step = self.get_task_step(sg, sg_publish["task"])
                        filter_step = step in step_list
                    if all((filter_entity, filter_task, filter_file_type, filter_path, filter_task_name, filter_step)):
                        publish_list.append(publish)
            else:
                filter_type = None
                publish_list = publishes
        return publish_list, filter_type

    def filter_asset_mdl(self, publishes, task):
        result = self.filter_publishes(publishes, task_list=[task], published_file_type_name_list=["Maya Scene"])
        publish_list = result[0]
        return publish_list

    def filter_asset_rig(self, publishes, sg):
        result = self.filter_publishes(publishes, sg=sg, published_file_type_name_list=["Alembic Cache"],
                                       step_list=["MDL"])
        publish_list = result[0]
        return publish_list

    def filter_asset_texture(self, publishes, sg, task):
        task_name = task["name"]
        suffix_list = list()
        if "_" in task_name:
            suffix = task_name.split("_")[-1]
            suffix_list.append(suffix)
        result = self.filter_publishes(publishes, sg=sg, published_file_type_name_list=["Alembic Cache"],
                                       task_name_suffix_list=suffix_list, step_list=["MDL"])
        publish_list = result[0]
        return publish_list

    def only_show_rig_and_gpu(self, publish_list, sg):
        rig_filter_list = self.filter_publishes(publish_list, sg=sg, step_list=["RIG", "MDL"],
                                                path_suffix_list=["Rig.ma", "_GPU.ma"])
        return rig_filter_list[0]

    def filter_shot_lay(self, publishes, sg, task):
        result = self.filter_publishes(publishes, filter_type="Shot", task_list=[task])
        publish_list, filter_type = result
        if filter_type:
            return publish_list
        else:
            return self.only_show_rig_and_gpu(publish_list, sg)

    def filter_shot_anim(self, publishes, sg):
        result = self.filter_publishes(publishes, sg=sg, step_list=["LAY"],
                                       path_suffix_list=["Layout.ma"], filter_type="Shot")
        publish_list, filter_type = result
        if filter_type:
            return publish_list
        else:
            return self.only_show_rig_and_gpu(publish_list, sg)

    def filter_shot_cfx(self, publishes, sg):
        result = self.filter_publishes(publishes, sg=sg, step_list=["ANM"], filter_type="Shot",
                                       published_file_type_name_list=["Alembic Cache"])
        publish_list, filter_type = result
        if filter_type:
            return publish_list
        else:
            asset_result = self.filter_publishes(publish_list, sg=sg, step_list=["MDL"],
                                                 published_file_type_name_list=["Alembic Cache"])
            return asset_result[0]

    def filter_shot_lgt(self, publishes, sg):
        result = self.filter_publishes(publishes, sg=sg, step_list=["ANM", "CFX", "VFX"], filter_type="Shot",
                                       published_file_type_name_list=["Alembic Cache"])
        publish_list, filter_type = result
        if filter_type:
            return publish_list
        else:
            asset_result = self.filter_publishes(publish_list, sg=sg, step_list=["Surface"],
                                                 path_suffix_list=["Surface.ma"])
            return asset_result[0]
