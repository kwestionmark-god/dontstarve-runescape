"""actions.action_system — ActionSystem class managing all player resource interaction actions."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from actions.types import ActionType, ActionState
from actions.active_action import ActiveAction
from actions.stamina import StaminaPool
from actions.notifications import ActionNotification

if TYPE_CHECKING:
    from world.resource_node import ResourceNode
    from skills.skill_manager import SkillManager
    from inventory.inventory import Inventory


class ActionSystem:
    """
    Manages all player resource interaction actions.

    Fields:
        active: The currently running action (None = idle)
        stamina: Stamina pool for woodcutting/mining
        notifications: Queue of notifications to display
        _pending_notifications: Internal buffer before flushing to notifications
    """

    __slots__ = (
        "active",
        "stamina",
        "notifications",
        "_pending_notifications",
        "survival",
        "_season_system",
        "weather_system",
    )

    def __init__(self) -> None:
        self.active: ActiveAction = ActiveAction(action_type=ActionType.WOODCUTTING)
        self.stamina = StaminaPool()
        self.notifications: List[ActionNotification] = []
        self._pending_notifications: List[ActionNotification] = []
        self.survival: object | None = None
        self._season_system: object | None = None
        self.weather_system: object | None = None

    def start_action(
        self,
        action_type: ActionType,
        resource: Optional["ResourceNode"],
        skill_manager: "SkillManager",
        inventory: "Inventory",
        recipe_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Start an action: checks tools, builds params, returns None or error string.

        This consolidates the tool-check + param-setting that game.py was
        doing with 11 separate field assignments.

        Args:
            action_type: The ActionType (WOODCUTTING/MINING/COOKING).
            resource: The ResourceNode to interact with (None for cooking).
            skill_manager: For stat-based success rate & bonus values.
            inventory: For equipped-tool detection.
            recipe_id: Cooking recipe id (only used for COOKING).

        Returns:
            Error message string if action cannot start, None on success.
        """
        # Already busy guard
        if self.active.state == ActionState.RUNNING:
            return "Already performing an action."

        # Cooldown guard: block re-gathering until the failure penalty elapses.
        # (update() decrements cooldown only while state != RUNNING; this makes the
        #  2s failure / 1s depletion-or-exhaustion penalty actually gate input.)
        if self.active.cooldown > 0:
            return "You must wait a moment before acting again."

        # Required-tool check (for gathering)
        if resource is not None and resource.requires_tool:
            tool = self._find_equipped_tool(inventory, resource.requires_tool)
            if tool is None:
                return f"You need a {resource.requires_tool}."

        # Build the action with correct parameters
        action = ActiveAction(action_type=action_type)

        if action_type == ActionType.WOODCUTTING and resource is not None:
            action.duration = 1.5
            action.resource = resource
            action.xp_reward = resource.xp_reward
            action.yield_item = resource.yield_item
            action.yield_quantity = resource.yield_quantity
            action.stamina_cost = 3.0
            action.required_tool = resource.requires_tool
            # Positive success_rate lowers the completion threshold (see
            # _complete_gathering), so spend stat points to harvest more easily.
            action.success_rate_bonus = -skill_manager.get_effective_stat(
                "woodcutting", "success_rate"
            ) * 1.0
            action.extra_resources_bonus = skill_manager.get_effective_stat(
                "woodcutting", "harvest_boost"
            )

        elif action_type == ActionType.MINING and resource is not None:
            action.duration = 2.0
            action.resource = resource
            action.xp_reward = resource.xp_reward
            action.yield_item = resource.yield_item
            action.yield_quantity = resource.yield_quantity
            action.stamina_cost = 3.0
            action.required_tool = resource.requires_tool
            action.success_rate_bonus = -skill_manager.get_effective_stat(
                "mining", "success_rate"
            ) * 1.0
            action.extra_resources_bonus = skill_manager.get_effective_stat(
                "mining", "extra_resources"
            )

        elif action_type == ActionType.COOKING and recipe_id is not None:
            action.duration = 3.0
            action.recipe_id = recipe_id
            action.xp_reward = 0.0
            action.yield_item = ""
            action.stamina_cost = 0.0

        else:
            return "No valid target."

        self.active = action
        self.active.state = ActionState.RUNNING
        self.active.elapsed = 0.0
        return None

    def process_completion(
        self,
        messages: List[str],
        inventory: "Inventory",
        skill_manager: "SkillManager",
        food_registry: "FoodRegistry | None" = None,
    ) -> None:
        """
        Process action-complete messages: add items, grant XP, show notifications.

        Parses messages of the form "action_complete:{item_id}:{quantity}:{xp}"
        and applies them to the inventory and skill manager.

        Args:
            messages: Feedback messages from action update.
            inventory: Player inventory to add items to.
            skill_manager: Skill manager for XP granting.
        """
        for msg in messages:
            if msg.startswith("action_complete:"):
                parts = msg.split(":")
                if len(parts) == 4:
                    item_id = parts[1]
                    quantity = int(parts[2])
                    xp = float(parts[3])

                    # Add yield to inventory
                    if not inventory.add_item(item_id, quantity):
                        self.add_notification(
                            "Inventory is full!", (255, 100, 100),
                        )
                    else:
                        self.add_notification(
                            f"+{quantity} {item_id}", (100, 255, 100),
                        )

                        # Perishable food harvested via gathering now spoils
                        # (previously only crafted/cooked food did).
                        if food_registry is not None:
                            food = food_registry.get(item_id)
                            if food is not None and food.spoilage_rate > 0:
                                inventory.set_spoilage(item_id, food.spoilage_rate)

                    # Determine skill from active resource
                    skill_id = self._action_type_to_skill_id()

                    # Delegate XP + level-up notification to SkillManager
                    skill_manager.add_xp_with_notification(
                        skill_id, xp,
                        lambda msg: self.add_notification(msg, (255, 215, 0)),
                    )

            else:
                # Regular message
                self.add_notification(msg)

    def _action_type_to_skill_id(self) -> str:
        """
        Map the active action's resource/tool to a skill ID string.

        Delegates to ActionType.get_skill_id() for the mapping logic.
        """
        return ActionType.get_skill_id(
            self.active.action_type, self.active.resource,
        )

    def update(self, dt: float) -> List[str]:
        """
        Update the active action. Called every frame.

        When an action completes, processes the result (success/failure),
        and returns feedback messages.

        Args:
            dt: Delta time in seconds.

        Returns:
            List of feedback messages for the player.
        """
        messages: List[str] = []

        if self.active.state != ActionState.RUNNING:
            # Process cooldown after failure
            if self.active.cooldown > 0:
                self.active.cooldown -= dt
                if self.active.cooldown <= 0:
                    self.active.state = ActionState.IDLE
                    self.active.elapsed = 0.0
            self.stamina.tick(dt)
            return messages

        # Progress the action
        self.active.elapsed += dt

        # Check for completion
        if self.active.elapsed >= self.active.duration:
            messages = self._complete_action()

        self.stamina.tick(dt)
        return messages

    def _complete_action(self) -> List[str]:
        """
        Process the result of a completed action.

        Returns:
            List of feedback messages.
        """
        messages: List[str] = []
        action = self.active

        if action.action_type == ActionType.WOODCUTTING or action.action_type == ActionType.MINING:
            messages = self._complete_gathering(action)

        # Reset to idle
        action.state = ActionState.IDLE
        action.elapsed = 0.0
        action.resource = None
        action.recipe_id = None
        return messages

    def _complete_gathering(
        self, action: ActiveAction,
    ) -> List[str]:
        """Process completion of a woodcutting or mining action."""
        messages: List[str] = []
        resource = action.resource

        if resource is None:
            return ["No resource to harvest."]

        # Check seasonal availability
        if self._season_system is not None:
            if not self._season_system.is_resource_available(resource.resource_id):
                messages.append(f"The {resource.name} is not available this season.")
                action.cooldown = 1.0
                return messages

        # Check depletion
        if resource.is_depleted:
            messages.append("The resource is depleted.")
            action.cooldown = 1.0
            return messages

        # Check stamina
        if not self.stamina.consume(action.stamina_cost):
            messages.append("You are too exhausted. Rest for a moment.")
            action.cooldown = 1.0
            return messages

        # Roll success: base_chance + success_rate_stat
        # Base chance is 50%, bonus is success_rate_stat * 1.0% per point
        import random
        success_threshold = 50.0 - action.success_rate_bonus
        if random.random() * 100 < success_threshold:
            # Success
            if not resource.harvest():
                messages.append("The resource is depleted.")
                return messages

            # Determine yield
            quantity = action.yield_quantity

            # Apply seasonal resource multiplier to yield
            if self._season_system is not None and resource is not None:
                season_mod = self._season_system.get_resource_multiplier(resource.category)
                quantity = max(1, int(quantity * season_mod))

            # Apply weather outdoor crafting modifier
            if self.weather_system is not None:
                effects = self.weather_system.get_effects()
                outdoor_mod = effects.get("outdoor_crafting", 1.0)
                quantity = max(1, int(quantity * outdoor_mod))

            # Extra resources roll: extra_resources_bonus gives +1 chance per point
            for _ in range(action.extra_resources_bonus):
                if random.random() * 100 < 50.0:  # 50% chance per bonus point
                    quantity += 1

            # Return yield info for Game layer to process
            messages.append(f"action_complete:{action.yield_item}:{quantity}:{action.xp_reward}")
            return messages

        else:
            # Failure — no yield, cooldown penalty
            messages.append("You fail to harvest the resource.")
            action.cooldown = 2.0
            return messages

    def _find_equipped_tool(
        self, inventory: Inventory, tool_type: str,
    ) -> Optional[str]:
        """
        Find a tool of the given type in the inventory.

        Args:
            inventory: Player's inventory.
            tool_type: Tool type to find ("axe", "pickaxe").

        Returns:
            Item ID of the tool if found, None otherwise.
        """
        # Exact id match or a suffix match ("stone_axe" for "axe") — NOT a
        # substring match: "axe" in "pickaxe" is True, which made a pickaxe
        # satisfy an axe requirement.
        def _matches(item_id: str) -> bool:
            return (
                item_id == tool_type
                or item_id.endswith(f"_{tool_type}")
            )

        for slot in inventory.slots:
            if slot is not None and slot.is_equipped:
                if _matches(slot.item_id or ""):
                    return slot.item_id
        # Also check non-equipped — allow use without explicit equipping
        for slot in inventory.slots:
            if slot is not None and slot.item_id is not None:
                if _matches(slot.item_id):
                    return slot.item_id
        return None

    @property
    def season_system(self) -> object | None:
        """Getter for season_system (set by bootstrap)."""
        return self._season_system

    @season_system.setter
    def season_system(self, value: object | None) -> None:
        """Setter for season_system (set by bootstrap)."""
        self._season_system = value

    def add_notification(self, text: str, color: tuple[int, int, int] = (255, 255, 255)) -> None:
        """
        Queue a notification to display.

        Args:
            text: Message text.
            color: RGB color for rendering.
        """
        self._pending_notifications.append(
            ActionNotification(text=text, color=color)
        )

    def flush_notifications(self) -> List[ActionNotification]:
        """
        Flush pending notifications into the active display queue.

        Returns:
            List of newly queued notifications.
        """
        result = list(self._pending_notifications)
        self.notifications.extend(result)
        self._pending_notifications.clear()
        return result

    def update_notifications(self, dt: float) -> List[ActionNotification]:
        """
        Tick active notifications. Expire old ones, collect new ones.

        Args:
            dt: Delta time in seconds.

        Returns:
            List of just-expired notifications (for cleanup).
        """
        # Flush new ones first
        self.flush_notifications()

        # Expire old notifications
        expired: List[ActionNotification] = []
        for notif in self.notifications:
            notif.elapsed += dt
            if notif.is_expired:
                expired.append(notif)

        self.notifications = [
            n for n in self.notifications if not n.is_expired
        ]
        return expired
